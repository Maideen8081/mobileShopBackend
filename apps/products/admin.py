from django.contrib import admin
from .models import Product, ProductFeature, CareInstruction, ProductVariant, VariantImage


class ProductFeatureInline(admin.TabularInline):
    model = ProductFeature
    extra = 1


class CareInstructionInline(admin.TabularInline):
    model = CareInstruction
    extra = 1


class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 1


class VariantImageInline(admin.TabularInline):
    model = VariantImage
    extra = 1


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('product_name', 'brand', 'model_number', 'category', 'common_image', 'is_published', 'is_trending')
    list_filter = ('is_published', 'is_trending', 'is_new_arrival', 'is_best_selling', 'category')
    search_fields = ('product_name', 'brand', 'model_number')
    inlines = [ProductFeatureInline, CareInstructionInline, ProductVariantInline]


@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):
    list_display = ('variant_name', 'product', 'color', 'price', 'stock_quantity', 'is_active')
    list_filter = ('is_active', 'color')
    search_fields = ('variant_name', 'product__product_name')
    inlines = [VariantImageInline]


@admin.register(VariantImage)
class VariantImageAdmin(admin.ModelAdmin):
    list_display = ('id', 'variant', 'is_main', 'created_at')
