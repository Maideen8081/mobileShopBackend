from django.db import transaction
from django.db.models import Count
from .models import Category, SubCategory


class CatalogInUseError(Exception):
    """Raised when deleting a category or sub category that products still use."""


def _plural(n, word):
    return f'{n} {word}{"" if n == 1 else "s"}'


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
    def annotated_categories():
        return Category.objects.annotate(
            sub_category_count=Count('sub_categories', distinct=True),
            product_count=Count('products', distinct=True),
        )

    @staticmethod
    def get_category_list():
        return CategoryService.annotated_categories().order_by('-created_at')

    @staticmethod
    def get_dropdown_categories():
        return Category.objects.filter(status='active').only('id', 'category_name').order_by('category_name')

    @staticmethod
    @transaction.atomic
    def delete_category(instance):
        """Delete a category and its sub categories. Refuses while products use it."""
        product_count = instance.products.count()
        if product_count:
            raise CatalogInUseError(
                f'"{instance.category_name}" still has {_plural(product_count, "product")}. '
                'Move or delete those products first, or mark the category inactive.'
            )
        sub_count = instance.sub_categories.count()
        image = instance.category_image
        instance.sub_categories.all().delete()
        instance.delete()
        if image:
            transaction.on_commit(lambda: image.delete(save=False))
        return sub_count

    @staticmethod
    def delete_sub_category(instance):
        product_count = instance.products.count()
        if product_count:
            raise CatalogInUseError(
                f'"{instance.sub_category_name}" is used by {_plural(product_count, "product")}. '
                'Move those products to another sub category first.'
            )
        instance.delete()
