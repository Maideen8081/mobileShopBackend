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
    order_id = serializers.IntegerField(source='id', read_only=True)
    product_count = serializers.SerializerMethodField()
    delivery_status = serializers.SerializerMethodField()
    est_delivery = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            'order_id', 'order_number', 'payment_status', 'payment_method',
            'order_status', 'delivery_status', 'grand_total', 'subtotal',
            'shipping_charge', 'tax', 'discount', 'product_count',
            'est_delivery', 'created_at',
        ]

    def get_product_count(self, obj):
        return obj.items.count()

    def get_delivery_status(self, obj):
        status_map = {
            'order_placed': 'Order Placed',
            'accepted': 'Accepted',
            'processing': 'Processing',
            'shipped': 'Shipped',
            'out_for_delivery': 'Out for Delivery',
            'delivered': 'Delivered',
            'cancelled': 'Cancelled',
        }
        return status_map.get(obj.order_status, obj.order_status)

    def get_est_delivery(self, obj):
        from datetime import timedelta
        est = obj.created_at + timedelta(days=5)
        return est.strftime('%d %b %Y')


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


class SimpleOrderItemSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    variant_id = serializers.IntegerField(required=False, allow_null=True)
    name = serializers.CharField(max_length=200)
    brand = serializers.CharField(max_length=100, required=False, allow_blank=True)
    price = serializers.DecimalField(max_digits=10, decimal_places=2)
    quantity = serializers.IntegerField(min_value=1)
    emoji = serializers.CharField(max_length=10, required=False, allow_blank=True)
    image = serializers.CharField(max_length=500, required=False, allow_blank=True)
    storage = serializers.CharField(max_length=50, required=False, allow_blank=True)
    ram = serializers.CharField(max_length=50, required=False, allow_blank=True)
    color = serializers.CharField(max_length=50, required=False, allow_blank=True)
    category = serializers.CharField(max_length=100, required=False, allow_blank=True)


class SimpleCreateOrderSerializer(serializers.Serializer):
    items = SimpleOrderItemSerializer(many=True)
    total = serializers.DecimalField(max_digits=12, decimal_places=2)
    subtotal = serializers.DecimalField(max_digits=12, decimal_places=2)
    shipping = serializers.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax = serializers.DecimalField(max_digits=12, decimal_places=2, default=0)
    payment_method = serializers.CharField(max_length=50, default='card')
    delivery_address_id = serializers.IntegerField(required=False, allow_null=True)
    discount = serializers.DecimalField(max_digits=12, decimal_places=2, default=0)
    coupon_code = serializers.CharField(max_length=50, required=False, allow_blank=True)


class OrderItemResponseSerializer(serializers.ModelSerializer):
    product_id = serializers.IntegerField(source='product.id', read_only=True, allow_null=True)
    variant_id = serializers.IntegerField(source='variant.id', read_only=True, allow_null=True)

    class Meta:
        model = OrderItem
        fields = [
            'id', 'product_id', 'variant_id', 'product_name', 'image',
            'selected_color', 'selected_ram', 'selected_storage',
            'quantity', 'price', 'total_price',
        ]


class SimpleOrderSerializer(serializers.ModelSerializer):
    order_id = serializers.IntegerField(source='id', read_only=True)
    customer_name = serializers.SerializerMethodField()
    customer_mobile = serializers.SerializerMethodField()
    items = OrderItemResponseSerializer(many=True, read_only=True)
    delivery_status = serializers.SerializerMethodField()
    payment_status_display = serializers.SerializerMethodField()
    delivery_partner = serializers.SerializerMethodField()
    tracking_id = serializers.SerializerMethodField()
    shipping_address = serializers.SerializerMethodField()
    delivery_address_text = serializers.SerializerMethodField()
    est_delivery = serializers.SerializerMethodField()
    delivered_at = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            'id', 'order_id', 'order_number', 'customer_name', 'customer_mobile',
            'grand_total', 'subtotal', 'shipping_charge', 'tax', 'discount',
            'delivery_status', 'payment_status', 'payment_status_display',
            'payment_method', 'items', 'shipping_address', 'delivery_address_text',
            'delivery_partner', 'tracking_id',
            'est_delivery', 'delivered_at', 'coupon_code',
            'created_at', 'updated_at',
        ]

    def get_customer_name(self, obj):
        if obj.user:
            return f'{obj.user.first_name} {obj.user.last_name}'.strip() or obj.user.email
        return 'Guest'

    def get_customer_mobile(self, obj):
        if obj.user and obj.user.mobile_number:
            return obj.user.mobile_number
        if obj.shipping_address and isinstance(obj.shipping_address, dict):
            return obj.shipping_address.get('phone', obj.shipping_address.get('mobile', '-'))
        return '-'

    def get_shipping_address(self, obj):
        if obj.shipping_address and isinstance(obj.shipping_address, dict):
            addr = obj.shipping_address
            return {
                'name': addr.get('name', addr.get('full_name', '')),
                'phone': addr.get('phone', addr.get('mobile', '')),
                'address_line1': addr.get('address_line1', ''),
                'address_line2': addr.get('address_line2', ''),
                'landmark': addr.get('landmark', ''),
                'city': addr.get('city', ''),
                'state': addr.get('state', ''),
                'pincode': addr.get('pincode', addr.get('zip_code', '')),
                'country': addr.get('country', 'India'),
            }
        return {}

    def get_delivery_address_text(self, obj):
        if obj.shipping_address and isinstance(obj.shipping_address, dict):
            addr = obj.shipping_address
            parts = [
                addr.get('address_line1', ''),
                addr.get('address_line2', ''),
                addr.get('city', ''),
                addr.get('state', ''),
                addr.get('pincode', addr.get('zip_code', '')),
            ]
            return ', '.join(p for p in parts if p)
        return '-'

    def get_delivery_status(self, obj):
        status_map = {
            'order_placed': 'Order Placed',
            'accepted': 'Accepted',
            'processing': 'Processing',
            'shipped': 'Shipped',
            'out_for_delivery': 'Out for Delivery',
            'delivered': 'Delivered',
            'cancelled': 'Cancelled',
        }
        return status_map.get(obj.order_status, obj.order_status)

    def get_payment_status_display(self, obj):
        return obj.get_payment_status_display()

    def get_delivery_partner(self, obj):
        return 'Standard Delivery'

    def get_tracking_id(self, obj):
        return obj.razorpay_order_id or ''

    def get_est_delivery(self, obj):
        from datetime import timedelta
        est = obj.created_at + timedelta(days=5)
        return est.strftime('%d %b %Y')

    def get_delivered_at(self, obj):
        if obj.order_status == 'delivered':
            return obj.updated_at.strftime('%d %b %Y, %I:%M %p') if obj.updated_at else None
        return None
