from rest_framework import serializers
from apps.products.models import Product, ProductVariant, VariantImage
from .models import Cart, CartItem
from apps.common.serializers import AbsoluteImageField, get_absolute_image_url


class CartItemSerializer(serializers.ModelSerializer):
    product_id = serializers.IntegerField(source='product.id', read_only=True)
    variation_id = serializers.IntegerField(source='variant.id', read_only=True)
    product_name = serializers.CharField(source='product.product_name', read_only=True)
    brand = serializers.CharField(source='product.brand', read_only=True)
    image = serializers.SerializerMethodField()
    selected_color = serializers.CharField(source='variant.color', read_only=True)
    selected_ram = serializers.CharField(source='variant.ram_size', read_only=True)
    selected_storage = serializers.CharField(source='variant.storage_size', read_only=True)
    quantity = serializers.IntegerField(read_only=True)
    price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    discount_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True, allow_null=True)
    total_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    stock_status = serializers.CharField(read_only=True)
    cart_item_id = serializers.IntegerField(source='id', read_only=True)

    class Meta:
        model = CartItem
        fields = [
            'cart_item_id', 'product_id', 'variation_id', 'product_name', 'brand',
            'image', 'selected_color', 'selected_ram', 'selected_storage',
            'quantity', 'price', 'discount_price', 'total_price', 'stock_status',
        ]

    def get_image(self, obj):
        main_image = VariantImage.objects.filter(variant=obj.variant, is_main=True).first()
        if not main_image:
            main_image = VariantImage.objects.filter(variant=obj.variant).first()
        if main_image and main_image.image:
            return get_absolute_image_url(main_image.image, self.context.get('request'))
        if obj.product.common_image:
            return get_absolute_image_url(obj.product.common_image, self.context.get('request'))
        return None


class CartSerializer(serializers.ModelSerializer):
    products = serializers.SerializerMethodField()
    subtotal = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    tax = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    shipping_charge = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    discount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    grand_total = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    quantity = serializers.IntegerField(source='total_quantity', read_only=True)
    cart_id = serializers.IntegerField(source='id', read_only=True)

    class Meta:
        model = Cart
        fields = [
            'cart_id', 'products', 'subtotal', 'tax', 'shipping_charge',
            'discount', 'grand_total', 'quantity',
        ]

    def get_products(self, obj):
        items = obj.items.select_related('product', 'variant__images').all()
        return CartItemSerializer(items, many=True, context=self.context).data


class AddToCartSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    variation_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1, default=1)

    def validate_product_id(self, value):
        if not Product.objects.filter(id=value, is_published=True).exists():
            raise serializers.ValidationError('Product not found.')
        return value

    def validate(self, data):
        try:
            variant = ProductVariant.objects.get(
                id=data['variation_id'],
                product_id=data['product_id'],
                is_active=True,
            )
        except ProductVariant.DoesNotExist:
            raise serializers.ValidationError('Product variation not found.')

        if variant.stock_quantity < 1:
            raise serializers.ValidationError('This product is out of stock.')

        if variant.stock_quantity < data['quantity']:
            raise serializers.ValidationError(
                f'Only {variant.stock_quantity} unit(s) available in stock.'
            )

        data['variant'] = variant
        return data


class UpdateCartQuantitySerializer(serializers.Serializer):
    cart_item_id = serializers.IntegerField()
    action = serializers.ChoiceField(choices=['increase', 'decrease'])
