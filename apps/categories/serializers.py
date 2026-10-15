from rest_framework import serializers
from .models import Category, SubCategory
from .validators import MAX_SUB_CATEGORIES_PER_CATEGORY, clean_catalog_name, validate_category_image
from apps.common.serializers import AbsoluteImageField


class SubCategorySerializer(serializers.ModelSerializer):
    parent_category_name = serializers.CharField(source='parent_category.category_name', read_only=True)
    product_count = serializers.SerializerMethodField()

    class Meta:
        model = SubCategory
        fields = ['id', 'parent_category', 'parent_category_name', 'sub_category_name', 'status', 'product_count', 'created_at']

    def get_product_count(self, obj):
        count = getattr(obj, 'product_count', None)
        return count if count is not None else obj.products.count()

    def validate_sub_category_name(self, value):
        return clean_catalog_name(value, 'Sub category name')

    def validate_parent_category(self, value):
        if self.instance and value != self.instance.parent_category:
            raise serializers.ValidationError('A sub category cannot be moved to another category.')
        if not self.instance and value.status == 'inactive':
            raise serializers.ValidationError('Cannot add a sub category to an inactive category.')
        return value

    def validate(self, attrs):
        parent = attrs.get('parent_category') or (self.instance and self.instance.parent_category)
        name = attrs.get('sub_category_name')
        if parent and name:
            dupes = SubCategory.objects.filter(parent_category=parent, sub_category_name__iexact=name)
            if self.instance:
                dupes = dupes.exclude(pk=self.instance.pk)
            if dupes.exists():
                raise serializers.ValidationError(
                    {'sub_category_name': f'"{name}" already exists in {parent.category_name}.'}
                )
        if parent and not self.instance and parent.sub_categories.count() >= MAX_SUB_CATEGORIES_PER_CATEGORY:
            raise serializers.ValidationError(
                {'parent_category': f'A category can have at most {MAX_SUB_CATEGORIES_PER_CATEGORY} sub categories.'}
            )
        return attrs


class CategoryWriteSerializer(serializers.ModelSerializer):
    """Create and update. An image is required on create; pass remove_image=true to clear it."""

    category_image = serializers.ImageField(required=False, validators=[validate_category_image])
    remove_image = serializers.BooleanField(required=False, default=False, write_only=True)

    class Meta:
        model = Category
        fields = ['category_name', 'category_image', 'status', 'remove_image']

    def validate_category_name(self, value):
        name = clean_catalog_name(value, 'Category name')
        dupes = Category.objects.filter(category_name__iexact=name)
        if self.instance:
            dupes = dupes.exclude(pk=self.instance.pk)
        if dupes.exists():
            raise serializers.ValidationError('A category with this name already exists.')
        return name

    def validate(self, attrs):
        if not self.instance:
            if not attrs.get('category_name'):
                raise serializers.ValidationError({'category_name': 'Category name is required.'})
            if not attrs.get('category_image'):
                raise serializers.ValidationError({'category_image': 'Category image is required.'})
        elif attrs.get('remove_image') and not attrs.get('category_image'):
            raise serializers.ValidationError(
                {'category_image': 'A category must keep an image. Upload a replacement instead of removing it.'}
            )
        return attrs

    def update(self, instance, validated_data):
        validated_data.pop('remove_image', None)
        new_image = validated_data.get('category_image')
        old_image = instance.category_image if new_image else None
        instance = super().update(instance, validated_data)
        if old_image and old_image.name != instance.category_image.name:
            old_image.delete(save=False)
        return instance

    def create(self, validated_data):
        validated_data.pop('remove_image', None)
        return super().create(validated_data)


class CategoryListSerializer(serializers.ModelSerializer):
    sub_category_count = serializers.IntegerField(read_only=True, default=0)
    product_count = serializers.IntegerField(read_only=True, default=0)
    category_image = AbsoluteImageField()

    class Meta:
        model = Category
        fields = ['id', 'category_name', 'category_image', 'status', 'sub_category_count', 'product_count', 'created_at']


class CategoryDetailSerializer(serializers.ModelSerializer):
    sub_category_count = serializers.IntegerField(read_only=True, default=0)
    product_count = serializers.IntegerField(read_only=True, default=0)
    category_image = AbsoluteImageField()
    subcategories = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = [
            'id', 'category_name', 'category_image', 'status', 'sub_category_count', 'product_count',
            'subcategories', 'created_at', 'updated_at',
        ]

    def get_subcategories(self, obj):
        subs = obj.sub_categories.order_by('created_at')
        return SubCategorySerializer(subs, many=True, context=self.context).data


class CategoryDropdownSerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'category_name']
