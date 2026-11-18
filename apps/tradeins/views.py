import os
from datetime import datetime

from django.db import transaction
from django.db.models import Count, Q, Sum
from django.utils import timezone
from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from apps.common.permissions import IsAdminUser

from .models import TradeIn, TradeInPhoto
from .serializers import (
    TradeInAcceptSerializer, TradeInAdminUpdateSerializer, TradeInCourierSerializer,
    TradeInCreateSerializer, TradeInNoteSerializer, TradeInPaySerializer,
    TradeInPaymentUploadSerializer, TradeInQuoteSerializer, TradeInRejectSerializer,
    TradeInSerializer, TradeInStatusSerializer,
)

ALLOWED_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp'}
MAX_IMAGE_BYTES = 5 * 1024 * 1024
PHOTO_KEYS = {
    'photo_front': TradeInPhoto.PHOTO_FRONT,
    'photo_back': TradeInPhoto.PHOTO_BACK,
    'photo_left': TradeInPhoto.PHOTO_LEFT,
    'photo_right': TradeInPhoto.PHOTO_RIGHT,
    'photo_box': TradeInPhoto.PHOTO_BOX,
}


def _ok(data, message='', code=status.HTTP_200_OK):
    body = {'success': True, 'data': data}
    if message:
        body['message'] = message
    return Response(body, status=code)


def _fail(message, code=status.HTTP_400_BAD_REQUEST):
    return Response({'success': False, 'message': message}, status=code)


def _serialize(trade, request=None, many=False):
    return TradeInSerializer(trade, many=many, context={'request': request}).data


def _image_error(upload, label):
    if not upload:
        return None
    extension = os.path.splitext(upload.name or '')[1].lower()
    if extension not in ALLOWED_IMAGE_EXTENSIONS:
        return f'{label} must be a JPG, PNG or WEBP image.'
    if upload.size > MAX_IMAGE_BYTES:
        return f'{label} must be smaller than 5 MB.'
    if upload.size == 0:
        return f'{label} is empty.'
    return None


def _validate_uploads(request, keys, required=()):
    for key in keys:
        upload = request.FILES.get(key)
        error = _image_error(upload, key.replace('_', ' ').title())
        if error:
            return None, error
        if key in required and not upload:
            return None, f'{key.replace("_", " ").title()} is required.'
    return True, None


def _save_photos(trade, request):
    for key, kind in PHOTO_KEYS.items():
        upload = request.FILES.get(key)
        if upload:
            TradeInPhoto.objects.create(trade=trade, kind=kind, image=upload)


class TradeInListCreateAPIView(GenericAPIView):
    """POST is open to shoppers (signed in or not); GET lists everything for admins."""

    serializer_class = TradeInCreateSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_permissions(self):
        return [AllowAny()] if self.request.method == 'POST' else [IsAdminUser()]

    def get(self, request):
        qs = TradeIn.objects.prefetch_related('photos').all()
        status_filter = request.query_params.get('status', '').strip()
        search = request.query_params.get('search', '').strip()
        if status_filter:
            qs = qs.filter(status=status_filter)
        if search:
            qs = qs.filter(
                Q(customer_name__icontains=search) | Q(customer_mobile__icontains=search)
                | Q(customer_email__icontains=search) | Q(device_brand__icontains=search)
                | Q(device_model__icontains=search) | Q(imei_number__icontains=search)
            )
        return _ok(_serialize(qs, request, many=True))

    def post(self, request):
        upload_keys = [*PHOTO_KEYS, 'purchase_bill']
        valid, error = _validate_uploads(request, upload_keys)
        if not valid:
            return _fail(error)

        serializer = TradeInCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = request.user if request.user.is_authenticated else None
        with transaction.atomic():
            trade = serializer.save(user=user)
            _save_photos(trade, request)
            purchase_bill = request.FILES.get('purchase_bill')
            if purchase_bill:
                trade.purchase_bill.save(purchase_bill.name, purchase_bill, save=False)
                trade.save(update_fields=['purchase_bill', 'updated_at'])
        return _ok(_serialize(trade, request), 'Trade-in request submitted.', status.HTTP_201_CREATED)


class MyTradeInsAPIView(GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = TradeInSerializer

    def get(self, request):
        trades = TradeIn.objects.filter(user=request.user).prefetch_related('photos')
        return _ok(_serialize(trades, request, many=True))


class _AdminTradeInView(GenericAPIView):
    permission_classes = [IsAdminUser]
    serializer_class = TradeInSerializer

    def get_trade(self, pk, lock=False):
        qs = TradeIn.objects.select_for_update() if lock else TradeIn.objects
        return qs.prefetch_related('photos').filter(pk=pk).first()

    def _transition(self, trade, new_status):
        if trade.status == new_status:
            return f'Trade-in is already {trade.get_status_display().lower()}.'
        if not trade.can_transition_to(new_status):
            return (
                f'Cannot move a {trade.get_status_display().lower()} trade-in to '
                f'{dict(TradeIn.STATUS_CHOICES)[new_status].lower()}.'
            )
        return None

    @staticmethod
    def _append_note(trade, notes):
        notes = (notes or '').strip()
        if notes:
            trade.admin_notes = f'{trade.admin_notes}\n{notes}'.strip() if trade.admin_notes else notes


class _CustomerTradeInView(GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = TradeInSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_trade(self, request, pk, lock=False):
        qs = TradeIn.objects.filter(user=request.user)
        if lock:
            qs = qs.select_for_update()
        return qs.prefetch_related('photos').filter(pk=pk).first()


class TradeInDetailAPIView(_AdminTradeInView):
    def get(self, request, pk):
        trade = self.get_trade(pk)
        if not trade:
            return _fail('Trade-in not found.', status.HTTP_404_NOT_FOUND)
        return _ok(_serialize(trade, request))

    def patch(self, request, pk):
        trade = self.get_trade(pk)
        if not trade:
            return _fail('Trade-in not found.', status.HTTP_404_NOT_FOUND)
        if trade.status in (TradeIn.STATUS_PAID, TradeIn.STATUS_REJECTED, TradeIn.STATUS_CANCELLED):
            return _fail(f'A {trade.get_status_display().lower()} trade-in can no longer be edited.')
        serializer = TradeInAdminUpdateSerializer(trade, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return _ok(_serialize(trade, request), 'Trade-in updated.')

    def delete(self, request, pk):
        trade = self.get_trade(pk)
        if not trade:
            return _fail('Trade-in not found.', status.HTTP_404_NOT_FOUND)
        if trade.status == TradeIn.STATUS_PAID:
            return _fail('Paid trade-ins are kept for accounting and cannot be deleted.')
        trade.delete()
        return _ok(None, 'Trade-in deleted.')


class TradeInVerifyAPIView(_AdminTradeInView):
    """Admin confirms the submitted device details, photos and IMEI."""

    def put(self, request, pk):
        serializer = TradeInNoteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            trade = self.get_trade(pk, lock=True)
            if not trade:
                return _fail('Trade-in not found.', status.HTTP_404_NOT_FOUND)
            error = self._transition(trade, TradeIn.STATUS_VERIFIED)
            if error:
                return _fail(error)
            trade.status = TradeIn.STATUS_VERIFIED
            trade.verified_at = timezone.now()
            self._append_note(trade, serializer.validated_data.get('notes'))
            trade.save()
        return _ok(_serialize(trade, request), 'Trade-in verified.')


class TradeInStatusAPIView(_AdminTradeInView):
    """Generic status move used by the dashboard's "advance" button. Moves that
    need extra data (accept → final value, reject → reason, paid → method) must
    use their dedicated endpoints."""

    def put(self, request, pk):
        serializer = TradeInStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        new_status = serializer.validated_data['status']
        with transaction.atomic():
            trade = self.get_trade(pk, lock=True)
            if not trade:
                return _fail('Trade-in not found.', status.HTTP_404_NOT_FOUND)
            if new_status == TradeIn.STATUS_ACCEPTED and trade.status == TradeIn.STATUS_PENDING:
                return _fail('Review the trade-in and set a quoted price before accepting.')
            error = self._transition(trade, new_status)
            if error:
                return _fail(error)
            if new_status == TradeIn.STATUS_ACCEPTED and not (trade.final_value or trade.quoted_price):
                return _fail('Set a quoted price or final value before accepting.')
            if new_status == TradeIn.STATUS_REJECTED:
                return _fail('Use the reject action and give a reason.')
            if new_status == TradeIn.STATUS_PAID:
                return _fail('Use the mark-as-paid action and choose a payment method.')
            if new_status == TradeIn.STATUS_ACCEPTED and not trade.final_value:
                trade.final_value = trade.quoted_price
            trade.status = new_status
            self._append_note(trade, serializer.validated_data.get('notes'))
            trade.save()
        return _ok(_serialize(trade, request), f'Trade-in marked {trade.get_status_display().lower()}.')


class TradeInQuoteAPIView(_AdminTradeInView):
    def put(self, request, pk):
        serializer = TradeInQuoteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            trade = self.get_trade(pk, lock=True)
            if not trade:
                return _fail('Trade-in not found.', status.HTTP_404_NOT_FOUND)
            if trade.status not in (
                TradeIn.STATUS_PENDING, TradeIn.STATUS_VERIFIED, TradeIn.STATUS_REVIEWED
            ):
                return _fail('Only pending, verified or quoted trade-ins can be quoted.')
            trade.quoted_price = serializer.validated_data['quoted_price']
            trade.status = TradeIn.STATUS_REVIEWED
            self._append_note(trade, serializer.validated_data.get('notes'))
            trade.save()
        return _ok(_serialize(trade, request), 'Quote saved.')


class TradeInAcceptAPIView(_AdminTradeInView):
    def put(self, request, pk):
        serializer = TradeInAcceptSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            trade = self.get_trade(pk, lock=True)
            if not trade:
                return _fail('Trade-in not found.', status.HTTP_404_NOT_FOUND)
            error = self._transition(trade, TradeIn.STATUS_ACCEPTED)
            if error:
                return _fail(error)
            trade.final_value = serializer.validated_data['final_value']
            trade.status = TradeIn.STATUS_ACCEPTED
            self._append_note(trade, serializer.validated_data.get('notes'))
            trade.save()
        return _ok(_serialize(trade, request), 'Trade-in accepted.')


class TradeInAcceptOfferAPIView(_CustomerTradeInView):
    """Shopper accepts the amount offered by the admin and starts the courier step."""

    def put(self, request, pk):
        serializer = TradeInNoteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            trade = self.get_trade(request, pk, lock=True)
            if not trade:
                return _fail('Trade-in not found.', status.HTTP_404_NOT_FOUND)
            error = self._transition(trade, TradeIn.STATUS_ACCEPTED)
            if error:
                return _fail(error)
            if not (trade.final_value or trade.quoted_price):
                return _fail('No offer has been made for this trade-in yet.')
            if not trade.final_value:
                trade.final_value = trade.quoted_price
            trade.status = TradeIn.STATUS_ACCEPTED
            self._append_note(trade, serializer.validated_data.get('notes'))
            trade.save()
        return _ok(_serialize(trade, request), 'Offer accepted. Please courier your device.')


class TradeInCourierAPIView(_CustomerTradeInView):
    """Shopper uploads the courier slip after posting the device."""

    def post(self, request, pk):
        serializer = TradeInCourierSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        valid, error = _validate_uploads(request, ['courier_slip'], required=['courier_slip'])
        if not valid:
            return _fail(error)
        with transaction.atomic():
            trade = self.get_trade(request, pk, lock=True)
            if not trade:
                return _fail('Trade-in not found.', status.HTTP_404_NOT_FOUND)
            error = self._transition(trade, TradeIn.STATUS_SHIPPED)
            if error:
                return _fail(error)
            courier_slip = request.FILES['courier_slip']
            trade.courier_slip.save(courier_slip.name, courier_slip, save=False)
            trade.status = TradeIn.STATUS_SHIPPED
            trade.shipped_at = timezone.now()
            self._append_note(trade, serializer.validated_data.get('notes'))
            trade.save()
        return _ok(_serialize(trade, request), 'Courier slip uploaded.')


class TradeInRejectAPIView(_AdminTradeInView):
    def put(self, request, pk):
        serializer = TradeInRejectSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            trade = self.get_trade(pk, lock=True)
            if not trade:
                return _fail('Trade-in not found.', status.HTTP_404_NOT_FOUND)
            error = self._transition(trade, TradeIn.STATUS_REJECTED)
            if error:
                return _fail(error)
            trade.rejection_reason = serializer.validated_data['rejection_reason']
            trade.status = TradeIn.STATUS_REJECTED
            trade.save()
        return _ok(_serialize(trade, request), 'Trade-in rejected.')


class TradeInReceiveAPIView(_AdminTradeInView):
    """Admin confirms the device was received from the courier."""

    def put(self, request, pk):
        serializer = TradeInNoteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            trade = self.get_trade(pk, lock=True)
            if not trade:
                return _fail('Trade-in not found.', status.HTTP_404_NOT_FOUND)
            error = self._transition(trade, TradeIn.STATUS_RECEIVED)
            if error:
                return _fail(error)
            trade.status = TradeIn.STATUS_RECEIVED
            trade.received_at = timezone.now()
            self._append_note(trade, serializer.validated_data.get('notes'))
            trade.save()
        return _ok(_serialize(trade, request), 'Device marked as received.')


class TradeInPayAPIView(_AdminTradeInView):
    """Legacy JSON pay endpoint and multipart payment-bill upload share this view."""

    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def put(self, request, pk):
        serializer = TradeInPaySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return self._pay(request, pk, serializer.validated_data, require_bill=False)

    def post(self, request, pk):
        serializer = TradeInPaymentUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        valid, error = _validate_uploads(request, ['payment_bill'], required=['payment_bill'])
        if not valid:
            return _fail(error)
        return self._pay(request, pk, serializer.validated_data, require_bill=True)

    def _pay(self, request, pk, data, require_bill):
        with transaction.atomic():
            trade = self.get_trade(pk, lock=True)
            if not trade:
                return _fail('Trade-in not found.', status.HTTP_404_NOT_FOUND)
            error = self._transition(trade, TradeIn.STATUS_PAID)
            if error:
                return _fail(error)
            if not trade.final_value:
                return _fail('Set the final value before marking as paid.')
            if require_bill:
                payment_bill = request.FILES['payment_bill']
                trade.payment_bill.save(payment_bill.name, payment_bill, save=False)
            trade.payment_method = data['payment_method']
            trade.payment_status = 'completed'
            trade.status = TradeIn.STATUS_PAID
            trade.paid_at = timezone.now()
            self._append_note(trade, data.get('notes'))
            trade.save()
        return _ok(_serialize(trade, request), 'Payment recorded.')


class TradeInDashboardCountsAPIView(_AdminTradeInView):
    def get(self, request):
        agg = TradeIn.objects.aggregate(
            total=Count('id'),
            pending=Count('id', filter=Q(status=TradeIn.STATUS_PENDING)),
            verified=Count('id', filter=Q(status=TradeIn.STATUS_VERIFIED)),
            reviewed=Count('id', filter=Q(status=TradeIn.STATUS_REVIEWED)),
            accepted=Count('id', filter=Q(status=TradeIn.STATUS_ACCEPTED)),
            shipped=Count('id', filter=Q(status=TradeIn.STATUS_SHIPPED)),
            received=Count('id', filter=Q(status=TradeIn.STATUS_RECEIVED)),
            rejected=Count('id', filter=Q(status=TradeIn.STATUS_REJECTED)),
            paid=Count('id', filter=Q(status=TradeIn.STATUS_PAID)),
            totalPayout=Sum('final_value', filter=Q(status=TradeIn.STATUS_PAID)),
        )
        agg['totalPayout'] = float(agg['totalPayout'] or 0)
        return _ok(agg)
