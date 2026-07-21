import logging

from django.contrib import admin, messages
from .models import Category, SubCategory

logger = logging.getLogger(__name__)


class SubCategoryInline(admin.TabularInline):
    model = SubCategory
    extra = 1


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('category_name', 'status', 'category_image_preview', 'created_at')
    list_filter = ('status',)
    search_fields = ('category_name',)
    inlines = [SubCategoryInline]

    def category_image_preview(self, obj):
        if obj.category_image:
            return '<img src="{}" width="50" height="50" style="object-fit:cover;" />'.format(obj.category_image.url)
        return '-'
    category_image_preview.allow_tags = True
    category_image_preview.short_description = 'Image'

    def save_model(self, request, obj, form, change):
        try:
            super().save_model(request, obj, form, change)
        except Exception as e:
            logger.error("Category save failed: %s", e, exc_info=True)
            messages.error(request, f'Upload failed: {e}')
            raise


@admin.register(SubCategory)
class SubCategoryAdmin(admin.ModelAdmin):
    list_display = ('sub_category_name', 'parent_category', 'status', 'created_at')
    list_filter = ('status', 'parent_category')
    search_fields = ('sub_category_name',)
