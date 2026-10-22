from django.db import transaction
from django.db.models import Count, Q, Sum
from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from apps.common.permissions import IsAdminUser

from .models import TradeIn
from .serializers import (
    TradeInAcceptSerializer, TradeInAdminUpdateSerializer, TradeInCreateSerializer,
    TradeInPaySerializer, TradeInQuoteSerializer, TradeInRejectSerializer,
    TradeInSerializer, TradeInStatusSerializer,
)


def _ok(data, message='', code=status.HTTP_200_OK):
    body = {'success': True, 'data': data}
    if message:
        body['message'] = message
    return Response(body, status=code)


def _fail(message, code=status.HTTP_400_BAD_REQUEST):
    return Response({'success': False, 'message': message}, status=code)


class TradeInListCreateAPIView(GenericAPIView):
    """POST is open to shoppers (signed in or not); GET lists everything for admins."""

    serializer_class = TradeInCreateSerializer

    def get_permissions(self):
        return [AllowAny()] if self.request.method == 'POST' else [IsAdminUser()]

    def get(self, request):
        qs = TradeIn.objects.all()
        status_filter = request.query_params.get('status', '').strip()
        search = request.query_params.get('search', '').strip()
        if status_filter:
            qs = qs.filter(status=status_filter)
        if search:
            qs = qs.filter(
                Q(customer_name__icontains=search) | Q(customer_mobile__icontains=search)
                | Q(customer_email__icontains=search) | Q(device_brand__icontains=search)
                | Q(device_model__icontains=search)
            )
        return _ok(TradeInSerializer(qs, many=True).data)

    def post(self, request):
        serializer = TradeInCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = request.user if request.user.is_authenticated else None
        trade = serializer.save(user=user)
        return _ok(TradeInSerializer(trade).data, 'Trade-in request submitted.', status.HTTP_201_CREATED)


class MyTradeInsAPIView(GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = TradeInSerializer

    def get(self, request):
        return _ok(TradeInSerializer(TradeIn.objects.filter(user=request.user), many=True).data)


class _AdminTradeInView(GenericAPIView):
    permission_classes = [IsAdminUser]
    serializer_class = TradeInSerializer

    def get_trade(self, pk, lock=False):
        qs = TradeIn.objects.select_for_update() if lock else TradeIn.objects
        return qs.filter(pk=pk).first()

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


class TradeInDetailAPIView(_AdminTradeInView):
    def get(self, request, pk):
        trade = self.get_trade(pk)
        if not trade:
            return _fail('Trade-in not found.', status.HTTP_404_NOT_FOUND)
        return _ok(TradeInSerializer(trade).data)

    def patch(self, request, pk):
        trade = self.get_trade(pk)
        if not trade:
            return _fail('Trade-in not found.', status.HTTP_404_NOT_FOUND)
        if trade.status in (TradeIn.STATUS_PAID, TradeIn.STATUS_REJECTED, TradeIn.STATUS_CANCELLED):
            return _fail(f'A {trade.get_status_display().lower()} trade-in can no longer be edited.')
        serializer = TradeInAdminUpdateSerializer(trade, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return _ok(TradeInSerializer(trade).data, 'Trade-in updated.')

    def delete(self, request, pk):
        trade = self.get_trade(pk)
        if not trade:
            return _fail('Trade-in not found.', status.HTTP_404_NOT_FOUND)
        if trade.status == TradeIn.STATUS_PAID:
            return _fail('Paid trade-ins are kept for accounting and cannot be deleted.')
        trade.delete()
        return _ok(None, 'Trade-in deleted.')


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
        return _ok(TradeInSerializer(trade).data, f'Trade-in marked {trade.get_status_display().lower()}.')


class TradeInQuoteAPIView(_AdminTradeInView):
    def put(self, request, pk):
        serializer = TradeInQuoteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            trade = self.get_trade(pk, lock=True)
            if not trade:
                return _fail('Trade-in not found.', status.HTTP_404_NOT_FOUND)
            if trade.status not in (TradeIn.STATUS_PENDING, TradeIn.STATUS_REVIEWED):
                return _fail('Only pending or reviewed trade-ins can be quoted.')
            trade.quoted_price = serializer.validated_data['quoted_price']
            trade.status = TradeIn.STATUS_REVIEWED
            self._append_note(trade, serializer.validated_data.get('notes'))
            trade.save()
        return _ok(TradeInSerializer(trade).data, 'Quote saved.')


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
        return _ok(TradeInSerializer(trade).data, 'Trade-in accepted.')


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
        return _ok(TradeInSerializer(trade).data, 'Trade-in rejected.')


class TradeInPayAPIView(_AdminTradeInView):
    def put(self, request, pk):
        serializer = TradeInPaySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            trade = self.get_trade(pk, lock=True)
            if not trade:
                return _fail('Trade-in not found.', status.HTTP_404_NOT_FOUND)
            error = self._transition(trade, TradeIn.STATUS_PAID)
            if error:
                return _fail(error)
            if not trade.final_value:
                return _fail('Set the final value before marking as paid.')
            trade.payment_method = serializer.validated_data['payment_method']
            trade.payment_status = 'completed'
            trade.status = TradeIn.STATUS_PAID
            self._append_note(trade, serializer.validated_data.get('notes'))
            trade.save()
        return _ok(TradeInSerializer(trade).data, 'Payment recorded.')


class TradeInDashboardCountsAPIView(_AdminTradeInView):
    def get(self, request):
        agg = TradeIn.objects.aggregate(
            total=Count('id'),
            pending=Count('id', filter=Q(status=TradeIn.STATUS_PENDING)),
            reviewed=Count('id', filter=Q(status=TradeIn.STATUS_REVIEWED)),
            accepted=Count('id', filter=Q(status=TradeIn.STATUS_ACCEPTED)),
            rejected=Count('id', filter=Q(status=TradeIn.STATUS_REJECTED)),
            paid=Count('id', filter=Q(status=TradeIn.STATUS_PAID)),
            totalPayout=Sum('final_value', filter=Q(status=TradeIn.STATUS_PAID)),
        )
        agg['totalPayout'] = float(agg['totalPayout'] or 0)
        return _ok(agg)
