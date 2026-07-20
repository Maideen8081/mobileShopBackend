import razorpay
from decouple import config
from rest_framework import serializers
from .models import Coupon, Order, OrderItem


class CouponApplySerializer(serializers.Serializer):
    code = serializers.CharField()
    subtotal = serializers.DecimalField(max_digits=12, decimal_places=2)

    def validate_code(self, value):
        try:
            coupon = Coupon.objects.get(code__iexact=value.strip())
        except Coupon.DoesNotExist:
            raise serializers.ValidationError('Invalid coupon code.')

        if not coupon.is_valid:
            raise serializers.ValidationError('This coupon has expired or is no longer valid.')

        return value

    def validate(self, data):
        try:
            coupon = Coupon.objects.get(code__iexact=data['code'].strip())
        except Coupon.DoesNotExist:
            raise serializers.ValidationError('Invalid coupon code.')

        if data['subtotal'] < coupon.minimum_amount:
            raise serializers.ValidationError(
                f'Minimum purchase amount of ₹{coupon.minimum_amount} required for this coupon.'
            )
        data['coupon'] = coupon
        return data


class OrderItemSerializer(serializers.ModelSerializer):
    product_id = serializers.IntegerField(source='product.id', read_only=True, allow_null=True)
    variation_id = serializers.IntegerField(source='variant.id', read_only=True, allow_null=True)

    class Meta:
        model = OrderItem
        fields = [
            'product_id', 'variation_id', 'product_name', 'image',
            'selected_color', 'selected_ram', 'selected_storage',
            'quantity', 'price', 'total_price',
        ]


class OrderSerializer(serializers.ModelSerializer):
    products = OrderItemSerializer(source='items', many=True, read_only=True)
    order_id = serializers.IntegerField(source='id', read_only=True)

    class Meta:
        model = Order
        fields = [
            'order_id', 'order_number', 'products', 'shipping_address',
            'payment_method', 'payment_status', 'order_status',
            'subtotal', 'tax', 'shipping_charge', 'discount', 'grand_total',
            'coupon_code', 'razorpay_order_id', 'razorpay_payment_id',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'order_number', 'payment_status', 'order_status',
            'subtotal', 'tax', 'shipping_charge', 'discount', 'grand_total',
            'coupon_code', 'razorpay_order_id', 'razorpay_payment_id',
            'created_at', 'updated_at',
        ]


class OrderListSerializer(serializers.ModelSerializer):
    product_count = serializers.SerializerMethodField()
    order_id = serializers.IntegerField(source='id', read_only=True)

    class Meta:
        model = Order
        fields = [
            'order_id', 'order_number', 'payment_status', 'order_status',
            'grand_total', 'product_count', 'created_at',
        ]

    def get_product_count(self, obj):
        return obj.items.count()


class CreateOrderSerializer(serializers.Serializer):
    address_id = serializers.IntegerField()
    coupon_code = serializers.CharField(required=False, allow_blank=True)
    razorpay_order_id = serializers.CharField()
    razorpay_payment_id = serializers.CharField()
    razorpay_signature = serializers.CharField()


class CreateRazorpayOrderSerializer(serializers.Serializer):
    coupon_code = serializers.CharField(required=False, allow_blank=True)


class VerifyPaymentSerializer(serializers.Serializer):
    razorpay_order_id = serializers.CharField()
    razorpay_payment_id = serializers.CharField()
    razorpay_signature = serializers.CharField()

    def validate(self, data):
        client = razorpay.Client(
            auth=(config('RAZORPAY_KEY_ID'), config('RAZORPAY_SECRET'))
        )
        params_dict = {
            'razorpay_order_id': data['razorpay_order_id'],
            'razorpay_payment_id': data['razorpay_payment_id'],
            'razorpay_signature': data['razorpay_signature'],
        }
        try:
            result = client.utility.verify_payment_signature(params_dict)
            if not result:
                raise serializers.ValidationError('Payment signature verification failed.')
        except Exception as e:
            raise serializers.ValidationError(f'Payment verification error: {str(e)}')
        return data
