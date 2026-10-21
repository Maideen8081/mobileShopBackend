import logging
from decimal import Decimal

from django.db.models import Prefetch, Value
from django.db.models.functions import Coalesce, NullIf
from rest_framework import serializers
from apps.products.models import Product, ProductVariant, VariantImage
from .models import Cart, CartItem
from apps.common.serializers import AbsoluteImageField, get_absolute_image_url

logger = logging.getLogger(__name__)


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
        images = getattr(obj, '_prefetched_variant_images', None)
        if images is None:
            images = VariantImage.objects.filter(variant=obj.variant).order_by('-is_main', 'id')
        main_image = next((img for img in images if img.is_main), None)
        if not main_image and images:
            main_image = images[0]
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
        items = (
            obj.items
            .select_related('product', 'variant')
            .prefetch_related(
                Prefetch(
                    'variant__images',
                    queryset=VariantImage.objects.order_by('-is_main', 'id'),
                    to_attr='_prefetched_variant_images',
                )
            )
        )
        return CartItemSerializer(items, many=True, context=self.context).data


class AddToCartSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    # Optional: product listing cards don't know variant ids, so a missing/0
    # variation_id falls back to the product's default variant.
    variation_id = serializers.IntegerField(required=False, allow_null=True, default=None)
    quantity = serializers.IntegerField(min_value=1, default=1)

    def validate_product_id(self, value):
        if not Product.objects.filter(id=value, is_published=True).exists():
            raise serializers.ValidationError('Product not found.')
        return value

    def validate(self, data):
        active_variants = ProductVariant.objects.filter(product_id=data['product_id'], is_active=True)
        if data.get('variation_id'):
            variant = active_variants.filter(id=data['variation_id']).first()
            if variant is None:
                raise serializers.ValidationError('Product variation not found.')
        else:
            # Cheapest in-stock variant by selling price, matching the
            # min_price shown on listings.
            selling_price = Coalesce(NullIf('discount_price', Value(Decimal('0'))), 'price')
            variant = (
                active_variants.filter(stock_quantity__gt=0).order_by(selling_price, 'id').first()
                or active_variants.order_by(selling_price, 'id').first()
            )
            if variant is None:
                raise serializers.ValidationError('This product is currently unavailable.')

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
