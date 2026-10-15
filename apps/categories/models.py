from django.db import models
from django.db.models.functions import Length, Lower
from django.db.models.lookups import GreaterThanOrEqual, LessThanOrEqual

from apps.common.models import TimeStampedModel
from .validators import NAME_MAX_LENGTH, NAME_MIN_LENGTH, NAME_PATTERN

STATUS_CHOICES = (
    ('active', 'Active'),
    ('inactive', 'Inactive'),
)


def _name_constraints(field, prefix):
    """DB-side copy of clean_catalog_name: length bounds and allowed characters."""
    return [
        models.CheckConstraint(
            condition=GreaterThanOrEqual(Length(field), NAME_MIN_LENGTH),
            name=f'{prefix}_name_min_length',
        ),
        models.CheckConstraint(
            condition=LessThanOrEqual(Length(field), NAME_MAX_LENGTH),
            name=f'{prefix}_name_max_length',
        ),
        models.CheckConstraint(
            condition=models.Q(**{f'{field}__regex': NAME_PATTERN.pattern}),
            name=f'{prefix}_name_allowed_chars',
        ),
        models.CheckConstraint(
            condition=models.Q(status__in=[c[0] for c in STATUS_CHOICES]),
            name=f'{prefix}_status_valid',
        ),
    ]


class Category(TimeStampedModel):
    STATUS_CHOICES = STATUS_CHOICES

    category_name = models.CharField(max_length=100, unique=True)
    category_image = models.ImageField(upload_to='categories/', null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')

    class Meta:
        db_table = 'categories'
        verbose_name_plural = 'Categories'
        ordering = ('-created_at',)
        indexes = [
            models.Index(fields=['status']),
        ]
        constraints = [
            models.UniqueConstraint(Lower('category_name'), name='category_name_unique_ci'),
            *_name_constraints('category_name', 'category'),
        ]

    def __str__(self):
        return self.category_name


class SubCategory(models.Model):
    STATUS_CHOICES = STATUS_CHOICES

    parent_category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='sub_categories')
    sub_category_name = models.CharField(max_length=100)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'sub_categories'
        verbose_name_plural = 'Sub Categories'
        ordering = ('-created_at',)
        indexes = [
            models.Index(fields=['parent_category']),
        ]
        constraints = [
            models.UniqueConstraint(
                'parent_category', Lower('sub_category_name'), name='sub_category_name_unique_per_parent_ci',
            ),
            *_name_constraints('sub_category_name', 'sub_category'),
        ]

    def __str__(self):
        return self.sub_category_name
