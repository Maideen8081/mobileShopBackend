import traceback
from django.contrib import admin
from django.contrib import messages
from .models import Category, SubCategory


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
            print(f"CATEGORY SAVE: name={obj.category_name}, image={obj.category_image}")
            if obj.category_image:
                print(f"IMAGE FILE: name={obj.category_image.name}, size={obj.category_image.size}")
            super().save_model(request, obj, form, change)
            print(f"CATEGORY SAVED SUCCESSFULLY: id={obj.id}")
            if obj.category_image:
                print(f"IMAGE URL AFTER SAVE: {obj.category_image.url}")
        except Exception as e:
            print(f"CATEGORY SAVE ERROR: {e}")
            print(f"TRACEBACK: {traceback.format_exc()}")
            messages.error(request, f'Upload failed: {e}')
            raise


@admin.register(SubCategory)
class SubCategoryAdmin(admin.ModelAdmin):
    list_display = ('sub_category_name', 'parent_category', 'status', 'created_at')
    list_filter = ('status', 'parent_category')
    search_fields = ('sub_category_name',)
