from rest_framework import serializers
from .models import Category, SubCategory
from .validators import validate_category_image


class SubCategorySerializer(serializers.ModelSerializer):
    parent_category_name = serializers.CharField(source='parent_category.category_name', read_only=True)

    class Meta:
        model = SubCategory
        fields = ['id', 'parent_category', 'parent_category_name', 'sub_category_name', 'status', 'created_at']

    def validate_sub_category_name(self, value):
        if not value.strip():
            raise serializers.ValidationError('Sub category name cannot be empty.')
        return value.strip()

    def validate_parent_category(self, value):
        if not value:
            raise serializers.ValidationError('Parent category is required.')
        if value.status == 'inactive':
            raise serializers.ValidationError('Cannot add sub category to an inactive category.')
        return value


class CategoryCreateSerializer(serializers.ModelSerializer):
    category_image = serializers.ImageField(required=False, validators=[validate_category_image])

    class Meta:
        model = Category
        fields = ['category_name', 'category_image', 'status']

    def validate_category_name(self, value):
        if not value.strip():
            raise serializers.ValidationError('Category name cannot be empty.')
        if Category.objects.filter(category_name__iexact=value.strip()).exists():
            raise serializers.ValidationError('A category with this name already exists.')
        return value.strip()


class CategoryUpdateSerializer(serializers.ModelSerializer):
    category_image = serializers.ImageField(required=False, validators=[validate_category_image])

    class Meta:
        model = Category
        fields = ['category_name', 'category_image', 'status']
        extra_kwargs = {
            'category_name': {'required': False},
        }

    def validate_category_name(self, value):
        if not value.strip():
            raise serializers.ValidationError('Category name cannot be empty.')
        instance = getattr(self, 'instance', None)
        qs = Category.objects.filter(category_name__iexact=value.strip())
        if instance:
            qs = qs.exclude(pk=instance.pk)
        if qs.exists():
            raise serializers.ValidationError('A category with this name already exists.')
        return value.strip()


class CategoryListSerializer(serializers.ModelSerializer):
    sub_category_count = serializers.IntegerField(read_only=True, default=0)
    product_count = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ['id', 'category_name', 'category_image', 'status', 'sub_category_count', 'product_count', 'created_at']

    def get_product_count(self, obj):
        try:
            return obj.products.count()
        except Exception:
            return 0


class CategoryDetailSerializer(serializers.ModelSerializer):
    sub_category_count = serializers.IntegerField(read_only=True)
    product_count = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ['id', 'category_name', 'category_image', 'status', 'sub_category_count', 'product_count', 'created_at', 'updated_at']

    def get_product_count(self, obj):
        try:
            return obj.products.count()
        except Exception:
            return 0


class CategoryDropdownSerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'category_name']
