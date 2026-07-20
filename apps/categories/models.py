from django.db import models
from apps.common.models import TimeStampedModel


class Category(TimeStampedModel):
    STATUS_CHOICES = (
        ('active', 'Active'),
        ('inactive', 'Inactive'),
    )

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

    def __str__(self):
        return self.category_name


class SubCategory(models.Model):
    STATUS_CHOICES = (
        ('active', 'Active'),
        ('inactive', 'Inactive'),
    )

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

    def __str__(self):
        return self.sub_category_name
