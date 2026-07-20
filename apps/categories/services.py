from django.db import transaction
from django.db.models import Count
from .models import Category, SubCategory


class CategoryService:

    @staticmethod
    def get_dashboard_counts():
        total = Category.objects.count()
        active = Category.objects.filter(status='active').count()
        inactive = Category.objects.filter(status='inactive').count()
        total_sub = SubCategory.objects.count()
        return {
            'total_categories': total,
            'active_categories': active,
            'inactive_categories': inactive,
            'total_sub_categories': total_sub,
        }

    @staticmethod
    def get_category_list():
        return Category.objects.annotate(
            sub_category_count=Count('sub_categories'),
        ).prefetch_related('sub_categories').order_by('-created_at')

    @staticmethod
    def get_dropdown_categories():
        return Category.objects.filter(status='active').only('id', 'category_name').order_by('category_name')

    @staticmethod
    def delete_category(instance):
        sub_count = instance.sub_categories.count()
        if sub_count > 0:
            instance.sub_categories.all().delete()
        instance.delete()
