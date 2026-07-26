from decouple import config
import razorpay
from django.db import transaction
from rest_framework import status
from rest_framework.generics import GenericAPIView, ListAPIView, RetrieveAPIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response

from apps.cart.models import Cart, CartItem
from apps.common.serializers import get_absolute_image_url
from apps.customers.models import Address
from apps.products.models import ProductVariant, VariantImage
from .models import Coupon, Order, OrderItem
from .serializers import (
    CouponApplySerializer,
    OrderSerializer,
    OrderListSerializer,
    CreateOrderSerializer,
    CreateRazorpayOrderSerializer,
    VerifyPaymentSerializer,
    SimpleCreateOrderSerializer,
    SimpleOrderSerializer,
)



class CouponApplyAPIView(GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = CouponApplySerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        coupon = serializer.validated_data['coupon']
        subtotal = serializer.validated_data['subtotal']

        if coupon.discount_type == 'percentage':
            discount = (coupon.discount_value / 100) * subtotal
        else:
            discount = coupon.discount_value

        if discount > subtotal:
            discount = subtotal

        return Response({
            'success': True,
            'data': {
                'coupon_code': coupon.code,
                'discount_type': coupon.discount_type,
                'discount_value': str(coupon.discount_value),
                'discount_amount': str(round(discount, 2)),
            },
        })


class CreateRazorpayOrderAPIView(GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = CreateRazorpayOrderSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = request.user
        try:
            cart = Cart.objects.get(user=user)
        except Cart.DoesNotExist:
            return Response({
                'success': False,
                'message': 'Cart is empty.',
            }, status=status.HTTP_400_BAD_REQUEST)

        items = cart.items.select_related('product', 'variant').all()
        if not items.exists():
            return Response({
                'success': False,
                'message': 'Cart is empty.',
            }, status=status.HTTP_400_BAD_REQUEST)

        for item in items:
            if item.quantity > item.variant.stock_quantity:
                return Response({
                    'success': False,
                    'message': f'Insufficient stock for {item.product.product_name}. '
                               f'Only {item.variant.stock_quantity} available.',
                }, status=status.HTTP_400_BAD_REQUEST)

        subtotal = cart.subtotal
        tax = cart.tax
        shipping_charge = cart.shipping_charge
        discount_amount = cart.discount

        coupon_code = serializer.validated_data.get('coupon_code', '')
        if coupon_code:
            try:
                coupon = Coupon.objects.get(code__iexact=coupon_code.strip())
                if coupon.is_valid and subtotal >= coupon.minimum_amount:
                    if coupon.discount_type == 'percentage':
                        coupon_discount = (coupon.discount_value / 100) * subtotal
                    else:
                        coupon_discount = coupon.discount_value
                    if coupon_discount > subtotal:
                        coupon_discount = subtotal
                    discount_amount += coupon_discount
            except Coupon.DoesNotExist:
                pass

        grand_total = subtotal + tax + shipping_charge - discount_amount
        if grand_total < 0:
            grand_total = 0

        amount_in_paise = int(grand_total * 100)

        client = razorpay.Client(auth=(config('RAZORPAY_KEY_ID'), config('RAZORPAY_SECRET')))

        try:
            razorpay_order = client.order.create({
                'amount': amount_in_paise,
                'currency': 'INR',
                'payment_capture': 1,
            })
        except Exception as e:
            return Response({
                'success': False,
                'message': f'Failed to create payment order: {str(e)}',
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({
            'success': True,
            'data': {
                'razorpay_order_id': razorpay_order['id'],
                'amount': razorpay_order['amount'],
                'currency': razorpay_order['currency'],
                'key_id': config('RAZORPAY_KEY_ID'),
                'subtotal': str(subtotal),
                'tax': str(tax),
                'shipping_charge': str(shipping_charge),
                'discount': str(discount_amount),
                'grand_total': str(grand_total),
            },
        })


class VerifyPaymentAPIView(GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = VerifyPaymentSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        return Response({
            'success': True,
            'message': 'Payment verified successfully.',
        })


class CreateOrderAPIView(GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = CreateOrderSerializer

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = request.user
        razorpay_order_id = serializer.validated_data['razorpay_order_id']
        razorpay_payment_id = serializer.validated_data['razorpay_payment_id']
        razorpay_signature = serializer.validated_data['razorpay_signature']

        try:
            cart = Cart.objects.get(user=user)
        except Cart.DoesNotExist:
            return Response({
                'success': False,
                'message': 'Cart is empty.',
            }, status=status.HTTP_400_BAD_REQUEST)

        cart_items = cart.items.select_related('product', 'variant__images').all()
        if not cart_items.exists():
            return Response({
                'success': False,
                'message': 'Cart is empty.',
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            address = Address.objects.get(id=serializer.validated_data['address_id'], user=user)
        except Address.DoesNotExist:
            return Response({
                'success': False,
                'message': 'Address not found.',
            }, status=status.HTTP_404_NOT_FOUND)

        for item in cart_items:
            if item.quantity > item.variant.stock_quantity:
                return Response({
                    'success': False,
                    'message': f'Insufficient stock for {item.product.product_name}.',
                }, status=status.HTTP_400_BAD_REQUEST)

        subtotal = cart.subtotal
        tax = cart.tax
        shipping_charge = cart.shipping_charge
        discount_amount = cart.discount
        coupon_obj = None
        coupon_code = serializer.validated_data.get('coupon_code', '')

        if coupon_code:
            try:
                coupon_obj = Coupon.objects.get(code__iexact=coupon_code.strip())
                if coupon_obj.is_valid and subtotal >= coupon_obj.minimum_amount:
                    if coupon_obj.discount_type == 'percentage':
                        coupon_discount = (coupon_obj.discount_value / 100) * subtotal
                    else:
                        coupon_discount = coupon_obj.discount_value
                    if coupon_discount > subtotal:
                        coupon_discount = subtotal
                    discount_amount += coupon_discount
            except Coupon.DoesNotExist:
                pass

        grand_total = subtotal + tax + shipping_charge - discount_amount
        if grand_total < 0:
            grand_total = 0

        order = Order.objects.create(
            user=user,
            shipping_address={
                    'name': address.full_name,
                    'phone': address.mobile_number,
                    'address_line1': address.house_number,
                    'address_line2': address.street_address,
                    'landmark': address.landmark,
                    'city': address.city,
                    'state': address.state,
                    'pincode': address.pincode,
                    'country': address.country,
                },
            address=address,
            payment_method='razorpay',
            payment_status='paid',
            order_status='order_placed',
            subtotal=subtotal,
            tax=tax,
            shipping_charge=shipping_charge,
            discount=discount_amount,
            grand_total=grand_total,
            coupon=coupon_obj,
            coupon_code=coupon_code,
            razorpay_order_id=razorpay_order_id,
            razorpay_payment_id=razorpay_payment_id,
            razorpay_signature=razorpay_signature,
        )

        for cart_item in cart_items:
            main_image = VariantImage.objects.filter(
                variant=cart_item.variant, is_main=True
            ).first()
            if not main_image:
                main_image = VariantImage.objects.filter(variant=cart_item.variant).first()
            image_url = ''
            if main_image and main_image.image:
                image_url = get_absolute_image_url(main_image.image, request)
            elif cart_item.product.common_image:
                image_url = get_absolute_image_url(cart_item.product.common_image, request)

            OrderItem.objects.create(
                order=order,
                product=cart_item.product,
                variant=cart_item.variant,
                product_name=cart_item.product.product_name,
                image=image_url,
                selected_color=cart_item.variant.color,
                selected_ram=cart_item.variant.ram_size,
                selected_storage=cart_item.variant.storage_size,
                quantity=cart_item.quantity,
                price=cart_item.price,
                total_price=cart_item.total_price,
            )

            variant = cart_item.variant
            variant.stock_quantity -= cart_item.quantity
            variant.save()

        if coupon_obj:
            Coupon.objects.filter(id=coupon_obj.id).update(used_count=coupon_obj.used_count + 1)

        cart.items.all().delete()
        cart.delete()

        order_serializer = OrderSerializer(order, context={'request': request})
        return Response({
            'success': True,
            'message': 'Order placed successfully.',
            'data': order_serializer.data,
        }, status=status.HTTP_201_CREATED)


class UserOrderListAPIView(ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = OrderListSerializer

    def get_queryset(self):
        return Order.objects.filter(user=self.request.user).prefetch_related('items')

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            'success': True,
            'data': serializer.data,
        })


class OrderDetailAPIView(RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = OrderSerializer

    def get_object(self):
        return Order.objects.filter(
            id=self.kwargs['order_id'],
            user=self.request.user,
        ).prefetch_related('items').first()

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        if not instance:
            return Response({
                'success': False,
                'message': 'Order not found.',
            }, status=status.HTTP_404_NOT_FOUND)
        serializer = self.get_serializer(instance)
        return Response({
            'success': True,
            'data': serializer.data,
        })


class SimpleCreateOrderAPIView(GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = SimpleCreateOrderSerializer

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        user = request.user

        address_obj = None
        shipping_addr = {}
        delivery_address_id = data.get('delivery_address_id')
        if delivery_address_id:
            try:
                address_obj = Address.objects.get(id=delivery_address_id, user=user)
                shipping_addr = {
                    'name': address_obj.full_name,
                    'phone': address_obj.mobile_number,
                    'address_line1': address_obj.house_number,
                    'address_line2': address_obj.street_address,
                    'landmark': address_obj.landmark,
                    'city': address_obj.city,
                    'state': address_obj.state,
                    'pincode': address_obj.pincode,
                    'country': address_obj.country,
                }
            except Address.DoesNotExist:
                return Response({
                    'success': False,
                    'message': 'Address not found.',
                }, status=status.HTTP_404_NOT_FOUND)

        payment_method = data.get('payment_method', 'card')
        payment_status = 'paid' if payment_method != 'cod' else 'pending'

        discount_amount = data.get('discount', 0)
        coupon_code = data.get('coupon_code', '')
        coupon_obj = None

        if coupon_code:
            try:
                coupon_obj = Coupon.objects.get(code__iexact=coupon_code.strip())
                if coupon_obj.is_valid and data['subtotal'] >= coupon_obj.minimum_amount:
                    if coupon_obj.discount_type == 'percentage':
                        coupon_discount = (coupon_obj.discount_value / 100) * data['subtotal']
                    else:
                        coupon_discount = coupon_obj.discount_value
                    if coupon_discount > data['subtotal']:
                        coupon_discount = data['subtotal']
                    discount_amount = coupon_discount
            except Coupon.DoesNotExist:
                pass

        grand_total = data['subtotal'] + data['tax'] + data['shipping'] - discount_amount
        if grand_total < 0:
            grand_total = 0

        order = Order.objects.create(
            user=user,
            shipping_address=shipping_addr,
            address=address_obj,
            payment_method=payment_method,
            payment_status=payment_status,
            order_status='order_placed',
            subtotal=data['subtotal'],
            tax=data['tax'],
            shipping_charge=data['shipping'],
            discount=discount_amount,
            grand_total=grand_total,
            coupon=coupon_obj,
            coupon_code=coupon_code,
        )

        for item_data in data['items']:
            OrderItem.objects.create(
                order=order,
                product_id=item_data['product_id'],
                variant_id=item_data.get('variant_id'),
                product_name=item_data['name'],
                image=item_data.get('image', ''),
                selected_color=item_data.get('color', ''),
                selected_ram=item_data.get('ram', ''),
                selected_storage=item_data.get('storage', ''),
                quantity=item_data['quantity'],
                price=item_data['price'],
                total_price=item_data['price'] * item_data['quantity'],
            )

        if coupon_obj:
            Coupon.objects.filter(id=coupon_obj.id).update(used_count=coupon_obj.used_count + 1)

        order_serializer = SimpleOrderSerializer(order)
        return Response({
            'success': True,
            'message': 'Order placed successfully.',
            'data': order_serializer.data,
        }, status=status.HTTP_201_CREATED)


class AllOrdersListAPIView(GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = SimpleOrderSerializer

    def get(self, request, *args, **kwargs):
        if request.user.is_staff or request.user.is_superuser:
            queryset = Order.objects.all().prefetch_related('items').order_by('-created_at')
        else:
            queryset = Order.objects.filter(user=request.user).prefetch_related('items').order_by('-created_at')

        search = request.query_params.get('search', '').strip()
        order_status = request.query_params.get('status', '').strip()
        payment_status = request.query_params.get('payment_status', '').strip()

        if search:
            from django.db.models import Q
            queryset = queryset.filter(
                Q(order_number__icontains=search) |
                Q(user__first_name__icontains=search) |
                Q(user__last_name__icontains=search) |
                Q(user__email__icontains=search) |
                Q(user__mobile_number__icontains=search)
            )
        if order_status:
            queryset = queryset.filter(order_status=order_status)
        if payment_status:
            queryset = queryset.filter(payment_status=payment_status)

        serializer = self.get_serializer(queryset, many=True)
        return Response({
            'success': True,
            'data': serializer.data,
        })


class OrderDetailByNumberAPIView(GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = SimpleOrderSerializer

    def get(self, request, order_id, *args, **kwargs):
        try:
            order = Order.objects.prefetch_related('items').get(id=order_id, user=request.user)
        except Order.DoesNotExist:
            return Response({
                'success': False,
                'message': 'Order not found.',
            }, status=status.HTTP_404_NOT_FOUND)

        serializer = self.get_serializer(order)
        return Response({
            'success': True,
            'data': serializer.data,
        })


class UpdateOrderStatusAPIView(GenericAPIView):
    permission_classes = [AllowAny]

    def put(self, request, order_number, *args, **kwargs):
        try:
            order = Order.objects.get(order_number=order_number)
        except Order.DoesNotExist:
            return Response({
                'success': False,
                'message': 'Order not found.',
            }, status=status.HTTP_404_NOT_FOUND)

        new_status = request.data.get('status', '').strip()
        valid_statuses = [choice[0] for choice in Order.ORDER_STATUS]
        if new_status not in valid_statuses:
            return Response({
                'success': False,
                'message': f'Invalid status. Must be one of: {", ".join(valid_statuses)}',
            }, status=status.HTTP_400_BAD_REQUEST)

        order.order_status = new_status
        if new_status == 'delivered':
            order.payment_status = 'paid'
        elif new_status == 'cancelled':
            order.payment_status = 'failed'
        order.save()

        serializer = SimpleOrderSerializer(order)
        return Response({
            'success': True,
            'message': f'Order status updated to {new_status}.',
            'data': serializer.data,
        })
