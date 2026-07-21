import json

from rest_framework import serializers
from .models import Product, ProductFeature, CareInstruction, ProductVariant, VariantImage
from apps.common.serializers import AbsoluteImageField


class VariantImageSerializer(serializers.ModelSerializer):
    image = AbsoluteImageField()

    class Meta:
        model = VariantImage
        fields = ['id', 'image', 'is_main']


class ProductVariantSerializer(serializers.ModelSerializer):
    images = VariantImageSerializer(many=True, read_only=True)
    image_count = serializers.SerializerMethodField()

    class Meta:
        model = ProductVariant
        fields = [
            'id', 'product', 'variant_name', 'color', 'ram_size', 'storage_size',
            'battery_capacity', 'processor', 'display_size', 'camera_details',
            'price', 'discount_price', 'stock_quantity', 'low_stock_alert',
            'is_active', 'created_at', 'updated_at', 'images', 'image_count',
        ]
        read_only_fields = ['product', 'created_at', 'updated_at']

    def get_image_count(self, obj):
        return obj.images.count()


class ProductFeatureSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductFeature
        fields = ['id', 'feature_text']


class CareInstructionSerializer(serializers.ModelSerializer):
    class Meta:
        model = CareInstruction
        fields = ['id', 'instruction_text']


class ProductListSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.category_name', read_only=True)
    sub_category_name = serializers.SerializerMethodField()
    variant_count = serializers.SerializerMethodField()
    total_stock = serializers.SerializerMethodField()
    min_price = serializers.SerializerMethodField()
    common_image = AbsoluteImageField()

    class Meta:
        model = Product
        fields = [
            'id', 'product_name', 'brand', 'model_number',
            'category', 'category_name', 'sub_category', 'sub_category_name',
            'common_image', 'is_trending', 'is_new_arrival', 'is_best_selling', 'is_featured', 'is_refurbished', 'is_published',
            'variant_count', 'total_stock', 'min_price',
            'created_at', 'updated_at',
        ]

    def get_sub_category_name(self, obj):
        return obj.sub_category.sub_category_name if obj.sub_category else None

    def get_variant_count(self, obj):
        return getattr(obj, 'variant_count', None) or obj.variants.count()

    def get_total_stock(self, obj):
        return getattr(obj, 'total_stock', None) or sum(
            obj.variants.values_list('stock_quantity', flat=True)
        )

    def get_min_price(self, obj):
        return getattr(obj, 'min_price', None)


class ProductDetailSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.category_name', read_only=True)
    sub_category_name = serializers.SerializerMethodField()
    features = ProductFeatureSerializer(many=True, read_only=True)
    care_instructions = CareInstructionSerializer(many=True, read_only=True)
    variants = ProductVariantSerializer(many=True, read_only=True)
    common_image = AbsoluteImageField()

    class Meta:
        model = Product
        fields = [
            'id', 'product_name', 'brand', 'model_number',
            'category', 'category_name', 'sub_category', 'sub_category_name',
            'description', 'common_image', 'is_trending', 'is_new_arrival', 'is_best_selling',
            'is_featured', 'is_refurbished', 'is_published', 'created_at', 'updated_at',
            'features', 'care_instructions', 'variants',
        ]

    def get_sub_category_name(self, obj):
        return obj.sub_category.sub_category_name if obj.sub_category else None


class ProductCreateSerializer(serializers.ModelSerializer):
    features = serializers.JSONField(required=False, write_only=True)
    care_instructions = serializers.JSONField(required=False, write_only=True)
    variants = serializers.JSONField(required=False, write_only=True)

    class Meta:
        model = Product
        fields = [
            'product_name', 'brand', 'model_number', 'category', 'sub_category',
            'description', 'common_image', 'is_trending', 'is_new_arrival', 'is_best_selling',
            'is_featured', 'is_refurbished', 'is_published', 'features', 'care_instructions', 'variants',
        ]

    def validate_product_name(self, value):
        if not value.strip():
            raise serializers.ValidationError('Product name cannot be empty.')
        return value.strip()

    def validate_brand(self, value):
        if not value.strip():
            raise serializers.ValidationError('Brand cannot be empty.')
        return value.strip()

    def validate_model_number(self, value):
        if not value.strip():
            raise serializers.ValidationError('Model number cannot be empty.')
        return value.strip()

    def validate_category(self, value):
        if not value:
            raise serializers.ValidationError('Category is required.')
        return value

    def validate_features(self, value):
        if not value:
            return []
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except json.JSONDecodeError:
                raise serializers.ValidationError('Invalid JSON format for features.')
        if not isinstance(value, list):
            raise serializers.ValidationError('Features must be a list.')
        for item in value:
            if not item.get('feature_text', '').strip():
                raise serializers.ValidationError('Feature text cannot be empty.')
        return value

    def validate_care_instructions(self, value):
        if not value:
            return []
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except json.JSONDecodeError:
                raise serializers.ValidationError('Invalid JSON format for care instructions.')
        if not isinstance(value, list):
            raise serializers.ValidationError('Care instructions must be a list.')
        for item in value:
            if not item.get('instruction_text', '').strip():
                raise serializers.ValidationError('Instruction text cannot be empty.')
        return value

    def validate_variants(self, value):
        if not value:
            return []
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except json.JSONDecodeError:
                raise serializers.ValidationError('Invalid JSON format for variants.')
        if not isinstance(value, list):
            raise serializers.ValidationError('Variants must be a list.')
        if len(value) < 1:
            raise serializers.ValidationError('At least one variant is required.')
        required_fields = ['variant_name', 'ram_size', 'storage_size', 'color',
                           'battery_capacity', 'processor', 'display_size',
                           'camera_details', 'price', 'stock_quantity']
        max_price = 99999999.99
        for i, v in enumerate(value):
            for field in required_fields:
                if field not in v or (isinstance(v.get(field), str) and not v[field].strip()):
                    raise serializers.ValidationError(
                        f'Variant {i + 1}: {field} is required.'
                    )
            price = float(v.get('price', 0))
            if price <= 0:
                raise serializers.ValidationError(f'Variant {i + 1}: Price must be greater than 0.')
            if price > max_price:
                raise serializers.ValidationError(f'Variant {i + 1}: Price exceeds maximum allowed value (99,999,999.99).')
            if int(v.get('stock_quantity', -1)) < 0:
                raise serializers.ValidationError(f'Variant {i + 1}: Stock cannot be negative.')
            if v.get('discount_price'):
                discount = float(v['discount_price'])
                if discount > max_price:
                    raise serializers.ValidationError(
                        f'Variant {i + 1}: Discount price exceeds maximum allowed value (99,999,999.99).'
                    )
                if discount > price:
                    raise serializers.ValidationError(
                        f'Variant {i + 1}: Discount price cannot exceed price.'
                    )
        return value

    def create(self, validated_data):
        features_data = validated_data.pop('features', [])
        care_data = validated_data.pop('care_instructions', [])
        variants_data = validated_data.pop('variants', [])

        product = Product.objects.create(**validated_data)

        for item in features_data:
            ProductFeature.objects.create(product=product, feature_text=item['feature_text'].strip())

        for item in care_data:
            CareInstruction.objects.create(product=product, instruction_text=item['instruction_text'].strip())

        for item in variants_data:
            ProductVariant.objects.create(product=product, **item)

        return product


class ProductUpdateSerializer(serializers.ModelSerializer):
    features = serializers.JSONField(required=False, write_only=True)
    care_instructions = serializers.JSONField(required=False, write_only=True)
    variants = serializers.JSONField(required=False, write_only=True)

    class Meta:
        model = Product
        fields = [
            'product_name', 'brand', 'model_number', 'category', 'sub_category',
            'description', 'common_image', 'is_trending', 'is_new_arrival', 'is_best_selling',
            'is_featured', 'is_refurbished', 'is_published', 'features', 'care_instructions', 'variants',
        ]
        extra_kwargs = {f: {'required': False} for f in fields}

    def validate_product_name(self, value):
        if not value.strip():
            raise serializers.ValidationError('Product name cannot be empty.')
        return value.strip()

    def validate_features(self, value):
        if not value:
            return []
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except json.JSONDecodeError:
                raise serializers.ValidationError('Invalid JSON format for features.')
        if not isinstance(value, list):
            raise serializers.ValidationError('Features must be a list.')
        for item in value:
            if not item.get('feature_text', '').strip():
                raise serializers.ValidationError('Feature text cannot be empty.')
        return value

    def validate_care_instructions(self, value):
        if not value:
            return []
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except json.JSONDecodeError:
                raise serializers.ValidationError('Invalid JSON format for care instructions.')
        if not isinstance(value, list):
            raise serializers.ValidationError('Care instructions must be a list.')
        for item in value:
            if not item.get('instruction_text', '').strip():
                raise serializers.ValidationError('Instruction text cannot be empty.')
        return value

    def validate_variants(self, value):
        if not value:
            return []
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except json.JSONDecodeError:
                raise serializers.ValidationError('Invalid JSON format for variants.')
        if not isinstance(value, list):
            raise serializers.ValidationError('Variants must be a list.')
        required_fields = ['variant_name', 'ram_size', 'storage_size', 'color',
                           'battery_capacity', 'processor', 'display_size',
                           'camera_details', 'price', 'stock_quantity']
        max_price = 99999999.99
        for i, v in enumerate(value):
            for field in required_fields:
                if field not in v or (isinstance(v.get(field), str) and not v[field].strip()):
                    raise serializers.ValidationError(
                        f'Variant {i + 1}: {field} is required.'
                    )
            price = float(v.get('price', 0))
            if price <= 0:
                raise serializers.ValidationError(f'Variant {i + 1}: Price must be greater than 0.')
            if price > max_price:
                raise serializers.ValidationError(f'Variant {i + 1}: Price exceeds maximum allowed value (99,999,999.99).')
            if int(v.get('stock_quantity', -1)) < 0:
                raise serializers.ValidationError(f'Variant {i + 1}: Stock cannot be negative.')
            if v.get('discount_price'):
                discount = float(v['discount_price'])
                if discount > max_price:
                    raise serializers.ValidationError(
                        f'Variant {i + 1}: Discount price exceeds maximum allowed value (99,999,999.99).'
                    )
                if discount > price:
                    raise serializers.ValidationError(
                        f'Variant {i + 1}: Discount price cannot exceed price.'
                    )
        return value

    def update(self, instance, validated_data):
        features_data = validated_data.pop('features', None)
        care_data = validated_data.pop('care_instructions', None)
        variants_data = validated_data.pop('variants', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if features_data is not None:
            instance.features.all().delete()
            for item in features_data:
                ProductFeature.objects.create(product=instance, feature_text=item['feature_text'].strip())

        if care_data is not None:
            instance.care_instructions.all().delete()
            for item in care_data:
                CareInstruction.objects.create(product=instance, instruction_text=item['instruction_text'].strip())

        if variants_data is not None:
            existing_ids = []
            for item in variants_data:
                variant_id = item.get('id')
                if variant_id:
                    try:
                        variant = ProductVariant.objects.get(id=variant_id, product=instance)
                        for attr, value in item.items():
                            if attr != 'id':
                                setattr(variant, attr, value)
                        variant.save()
                        existing_ids.append(variant_id)
                    except ProductVariant.DoesNotExist:
                        variant = ProductVariant.objects.create(product=instance, **item)
                        existing_ids.append(variant.id)
                else:
                    variant = ProductVariant.objects.create(product=instance, **item)
                    existing_ids.append(variant.id)
            instance.variants.exclude(id__in=existing_ids).delete()

        return instance
