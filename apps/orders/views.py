from decouple import config
from django.db import transaction
from rest_framework import status
from rest_framework.generics import GenericAPIView, ListAPIView, RetrieveAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.cart.models import Cart, CartItem
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
                'full_name': address.full_name,
                'mobile': address.mobile_number,
                'address_line1': address.house_number,
                'address_line2': address.street_address,
                'landmark': address.landmark,
                'city': address.city,
                'state': address.state,
                'zip_code': address.pincode,
                'country': address.country,
            },
            address=address,
            payment_method='razorpay',
            payment_status='paid',
            order_status='processing',
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
                image_url = request.build_absolute_uri(main_image.image.url)
            elif cart_item.product.common_image:
                image_url = request.build_absolute_uri(cart_item.product.common_image.url)

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
