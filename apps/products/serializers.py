import json
import re
from decimal import Decimal

from django.db.models import Q
from rest_framework import serializers

from apps.categories.models import SubCategory
from apps.common.serializers import AbsoluteImageField
from . import validators as rules
from .models import Product, ProductFeature, CareInstruction, ProductVariant, VariantImage, StockNotification


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
        count = getattr(obj, 'variant_count', None)
        return count if count is not None else obj.variants.filter(is_active=True).count()

    def get_total_stock(self, obj):
        total = getattr(obj, 'total_stock', None)
        if total is not None:
            return total
        return sum(obj.variants.values_list('stock_quantity', flat=True))

    def get_min_price(self, obj):
        return getattr(obj, 'min_price', None)

    def to_representation(self, obj):
        data = super().to_representation(obj)
        # Admin listing asks for variants inline (?include=variants) to avoid one request per product.
        if self.context.get('include_variants'):
            data['variants'] = ProductVariantSerializer(obj.variants.all(), many=True, context=self.context).data
        return data


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


TEXT_FIELD_LIMITS = {
    # field: (label, max length) — every one of these is required on a variant.
    'variant_name': ('Variant name', 100),
    'color': ('Color', 50),
    'ram_size': ('RAM size', 20),
    'storage_size': ('Storage size', 20),
    'processor': ('Processor', 100),
    'display_size': ('Display size', 50),
    'camera_details': ('Camera details', 255),
}
IMAGE_TOKEN = re.compile(r'^(id|file):(\d+)$')


class VariantInputSerializer(serializers.Serializer):
    """One variant as sent by the admin form. Unknown keys are ignored, never written."""

    id = serializers.IntegerField(required=False, allow_null=True)
    variant_name = serializers.CharField(max_length=100, trim_whitespace=True)
    color = serializers.CharField(max_length=50, trim_whitespace=True)
    ram_size = serializers.CharField(max_length=20, trim_whitespace=True)
    storage_size = serializers.CharField(max_length=20, trim_whitespace=True)
    battery_capacity = serializers.IntegerField(
        min_value=rules.BATTERY_MIN, max_value=rules.BATTERY_MAX,
        error_messages={
            'min_value': f'Battery capacity must be at least {rules.BATTERY_MIN} mAh.',
            'max_value': f'Battery capacity must be at most {rules.BATTERY_MAX} mAh.',
            'invalid': 'Battery capacity must be a whole number of mAh.',
        },
    )
    processor = serializers.CharField(max_length=100, trim_whitespace=True)
    display_size = serializers.CharField(max_length=50, trim_whitespace=True)
    camera_details = serializers.CharField(max_length=255, trim_whitespace=True)
    price = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=Decimal('0.01'), max_value=rules.PRICE_MAX,
        error_messages={'min_value': 'Price must be greater than 0.', 'max_value': 'Price is too large.'},
    )
    discount_price = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=Decimal('0'), max_value=rules.PRICE_MAX,
        required=False, allow_null=True,
    )
    stock_quantity = serializers.IntegerField(
        min_value=0, max_value=rules.STOCK_MAX,
        error_messages={'min_value': 'Stock cannot be negative.', 'max_value': f'Stock cannot exceed {rules.STOCK_MAX}.'},
    )
    low_stock_alert = serializers.IntegerField(min_value=0, max_value=rules.LOW_STOCK_ALERT_MAX, required=False, default=5)
    is_active = serializers.BooleanField(required=False, default=True)
    image_order = serializers.ListField(child=serializers.CharField(), required=False, allow_null=True)

    def validate(self, attrs):
        discount = attrs.get('discount_price')
        if discount is not None and discount <= 0:
            attrs['discount_price'] = None  # 0 means "no discount"
        elif discount is not None and discount >= attrs['price']:
            raise serializers.ValidationError({'discount_price': 'Discount price must be lower than the price.'})
        for token in attrs.get('image_order') or []:
            if not IMAGE_TOKEN.match(token):
                raise serializers.ValidationError({'image_order': f'Invalid image reference "{token}".'})
        return attrs


def _parse_json_list(value, label):
    if value in (None, ''):
        return []
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            raise serializers.ValidationError(f'Invalid JSON for {label}.')
    if not isinstance(value, list):
        raise serializers.ValidationError(f'{label.capitalize()} must be a list.')
    return value


def _text_items(value, key, label, max_items, max_len):
    items = []
    for raw in _parse_json_list(value, label):
        text = raw.get(key) if isinstance(raw, dict) else raw
        text = ' '.join(str(text or '').split())
        if not text:
            raise serializers.ValidationError(f'{label.capitalize()} cannot be empty.')
        if len(text) > max_len:
            raise serializers.ValidationError(f'Each {label[:-1]} must be at most {max_len} characters.')
        items.append(text)
    if len(items) > max_items:
        raise serializers.ValidationError(f'At most {max_items} {label} are allowed.')
    return items


class ProductWriteSerializer(serializers.ModelSerializer):
    """Create and update a product with its features, care instructions and variants.

    Variant images are uploaded as `variant_images` files. Each variant lists its
    images in display order in `image_order`: "id:<n>" keeps an existing image,
    "file:<k>" uses the k-th uploaded file. The first image becomes the main one.
    On update, a variant without `image_order` keeps its images unchanged.
    """

    features = serializers.JSONField(required=False, write_only=True)
    care_instructions = serializers.JSONField(required=False, write_only=True)
    variants = serializers.JSONField(required=False, write_only=True)
    common_image = serializers.ImageField(required=False, allow_null=True, validators=[rules.validate_product_image])
    remove_common_image = serializers.BooleanField(required=False, default=False, write_only=True)

    class Meta:
        model = Product
        fields = [
            'product_name', 'brand', 'model_number', 'category', 'sub_category',
            'description', 'common_image', 'remove_common_image',
            'is_trending', 'is_new_arrival', 'is_best_selling', 'is_featured', 'is_refurbished', 'is_published',
            'features', 'care_instructions', 'variants',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance is not None:
            for field in self.fields.values():
                field.required = False

    # ── field validators ──

    def validate_product_name(self, value):
        name = ' '.join(value.split())
        if len(name) < rules.PRODUCT_NAME_MIN:
            raise serializers.ValidationError(f'Product name must be at least {rules.PRODUCT_NAME_MIN} characters.')
        if len(name) > rules.PRODUCT_NAME_MAX:
            raise serializers.ValidationError(f'Product name must be at most {rules.PRODUCT_NAME_MAX} characters.')
        return name

    def validate_brand(self, value):
        brand = ' '.join(value.split())
        if len(brand) < rules.BRAND_MIN:
            raise serializers.ValidationError(f'Brand must be at least {rules.BRAND_MIN} characters.')
        if len(brand) > rules.BRAND_MAX:
            raise serializers.ValidationError(f'Brand must be at most {rules.BRAND_MAX} characters.')
        return brand

    def validate_model_number(self, value):
        model = value.strip()
        if not model:
            raise serializers.ValidationError('Model number is required.')
        if len(model) > rules.MODEL_NUMBER_MAX:
            raise serializers.ValidationError(f'Model number must be at most {rules.MODEL_NUMBER_MAX} characters.')
        if not rules.MODEL_NUMBER_PATTERN.match(model):
            raise serializers.ValidationError(
                'Model number must start with a letter or number and may only contain letters, numbers, spaces and . _ / + -'
            )
        return model

    def validate_description(self, value):
        value = (value or '').strip()
        if len(value) > rules.DESCRIPTION_MAX:
            raise serializers.ValidationError(f'Description must be at most {rules.DESCRIPTION_MAX} characters.')
        return value

    def validate_features(self, value):
        return _text_items(value, 'feature_text', 'features', rules.MAX_FEATURES, rules.FEATURE_MAX)

    def validate_care_instructions(self, value):
        return _text_items(
            value, 'instruction_text', 'care instructions', rules.MAX_CARE_INSTRUCTIONS, rules.CARE_INSTRUCTION_MAX,
        )

    def validate_variants(self, value):
        items = _parse_json_list(value, 'variants')
        if not items:
            raise serializers.ValidationError('At least one variant is required.')
        if len(items) > rules.MAX_VARIANTS:
            raise serializers.ValidationError(f'At most {rules.MAX_VARIANTS} variants are allowed.')
        cleaned, errors = [], {}
        for i, item in enumerate(items):
            s = VariantInputSerializer(data=item if isinstance(item, dict) else {})
            if s.is_valid():
                cleaned.append(s.validated_data)
            else:
                errors[i] = s.errors
        if errors:
            # Flatten into readable messages: "Variant 2: price — Price must be greater than 0."
            raise serializers.ValidationError([
                f'Variant {i + 1}: {field.replace("_", " ")} — {msgs[0]}'
                for i, errs in errors.items() for field, msgs in errs.items()
            ])
        return cleaned

    # ── cross-field validation ──

    def validate(self, attrs):
        instance = self.instance
        category = attrs.get('category', instance.category if instance else None)
        sub_category = attrs.get('sub_category', instance.sub_category if instance else None)

        if category is None:
            raise serializers.ValidationError({'category': 'Category is required.'})
        if 'category' in attrs and category.status != 'active' and (not instance or instance.category_id != category.id):
            raise serializers.ValidationError({'category': 'Choose an active category.'})
        if sub_category is not None and sub_category.parent_category_id != category.id:
            raise serializers.ValidationError({'sub_category': f'This sub category does not belong to {category.category_name}.'})
        if sub_category is None and SubCategory.objects.filter(parent_category=category).exists():
            raise serializers.ValidationError({'sub_category': f'Choose a sub category of {category.category_name}.'})

        brand = attrs.get('brand', instance.brand if instance else None)
        model = attrs.get('model_number', instance.model_number if instance else None)
        if brand and model:
            dupes = Product.objects.filter(brand__iexact=brand, model_number__iexact=model)
            if instance:
                dupes = dupes.exclude(pk=instance.pk)
            if dupes.exists():
                raise serializers.ValidationError(
                    {'model_number': f'A {brand} product with model number "{model}" already exists.'}
                )

        if attrs.get('remove_common_image') and attrs.get('common_image'):
            raise serializers.ValidationError({'common_image': 'Upload a new cover image or remove it, not both.'})

        if not instance and 'variants' not in attrs:
            raise serializers.ValidationError({'variants': 'At least one variant is required.'})
        if 'variants' in attrs:
            self._validate_variant_set(attrs['variants'])
        return attrs

    def _uploaded_files(self):
        request = self.context.get('request')
        return request.FILES.getlist('variant_images') if request else []

    def _validate_variant_set(self, variants):
        instance = self.instance
        files = self._uploaded_files()
        for f in files:
            try:
                rules.validate_product_image(f)
            except Exception as exc:  # Django ValidationError
                raise serializers.ValidationError({'variant_images': f'{f.name}: {"; ".join(getattr(exc, "messages", [str(exc)]))}'})

        existing = {}
        if instance:
            existing = {v.id: v for v in instance.variants.prefetch_related('images')}
        combos, used_files, errors = set(), set(), []
        for i, v in enumerate(variants):
            label = f'Variant {i + 1}'
            vid = v.get('id')
            if vid and vid not in existing:
                errors.append(f'{label}: does not belong to this product.')
                continue
            combo = (v['color'].lower(), v['ram_size'].lower(), v['storage_size'].lower())
            if combo in combos:
                errors.append(f'{label}: another variant already has {v["color"]} / {v["ram_size"]} / {v["storage_size"]}.')
            combos.add(combo)

            order = v.get('image_order')
            if order is None:
                if not vid:
                    errors.append(f'{label}: at least one image is required.')
                continue
            own_ids = {img.id for img in existing[vid].images.all()} if vid else set()
            for token in order:
                kind, num = token.split(':')
                num = int(num)
                if kind == 'id' and num not in own_ids:
                    errors.append(f'{label}: image {num} does not belong to this variant.')
                elif kind == 'file':
                    if num >= len(files):
                        errors.append(f'{label}: uploaded image #{num + 1} is missing.')
                    elif num in used_files:
                        errors.append(f'{label}: an uploaded image is assigned to two variants.')
                    used_files.add(num)
            if len(order) < 1:
                errors.append(f'{label}: at least one image is required.')
            elif len(order) > rules.MAX_IMAGES_PER_VARIANT:
                errors.append(f'{label}: at most {rules.MAX_IMAGES_PER_VARIANT} images are allowed.')
        if errors:
            raise serializers.ValidationError({'variants': errors})

    # ── persistence (callers wrap save() in a transaction) ──

    def create(self, validated_data):
        validated_data.pop('remove_common_image', None)
        nested = self._pop_nested(validated_data)
        product = Product.objects.create(**validated_data)
        self._save_nested(product, nested)
        return product

    def update(self, instance, validated_data):
        nested = self._pop_nested(validated_data)
        if validated_data.pop('remove_common_image', False):
            instance.common_image = None
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        self._save_nested(instance, nested)
        return instance

    @staticmethod
    def _pop_nested(validated_data):
        return {key: validated_data.pop(key, None) for key in ('features', 'care_instructions', 'variants')}

    def _save_nested(self, product, nested):
        if nested['features'] is not None:
            product.features.all().delete()
            ProductFeature.objects.bulk_create(ProductFeature(product=product, feature_text=t) for t in nested['features'])
        if nested['care_instructions'] is not None:
            product.care_instructions.all().delete()
            CareInstruction.objects.bulk_create(
                CareInstruction(product=product, instruction_text=t) for t in nested['care_instructions']
            )
        if nested['variants'] is not None:
            self._save_variants(product, nested['variants'])

    def _save_variants(self, product, variants):
        files = self._uploaded_files()
        keep_ids = []
        for data in variants:
            data = dict(data)
            vid = data.pop('id', None)
            order = data.pop('image_order', None)
            data['battery_capacity'] = str(data['battery_capacity'])
            if vid:
                variant = product.variants.get(pk=vid)
                for attr, value in data.items():
                    setattr(variant, attr, value)
                variant.save()
            else:
                variant = ProductVariant.objects.create(product=product, **data)
            keep_ids.append(variant.id)
            if order is not None:
                self._apply_image_order(variant, order, files)
        # Variants dropped from the form are removed. Order history keeps its own
        # snapshot (OrderItem.product_name/price/...), so this is safe for past orders.
        product.variants.exclude(id__in=keep_ids).delete()

    @staticmethod
    def _apply_image_order(variant, order, files):
        kept = []
        for position, token in enumerate(order):
            kind, num = token.split(':')
            if kind == 'id':
                img = variant.images.get(pk=int(num))
            else:
                img = VariantImage(variant=variant, image=files[int(num)])
            img.is_main = position == 0
            img.save()
            kept.append(img.id)
        # Image files are left in storage: past order items link to them by URL.
        variant.images.exclude(id__in=kept).delete()


def admin_product_queryset():
    """Products with everything the admin list renders, in two queries."""
    return Product.objects.select_related('category', 'sub_category').prefetch_related('variants__images')


def published_filter():
    """What shoppers may see: published products in active categories."""
    return Q(is_published=True, category__status='active')


class StockNotificationSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)
    variant_id = serializers.IntegerField(required=False, allow_null=True)

    def validate_email(self, value):
        return value.strip().lower()
