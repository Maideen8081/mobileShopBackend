from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.common.models import TimeStampedModel
from apps.products.models import Product


class Review(TimeStampedModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='reviews',
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='reviews',
    )
    star = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    rating = models.CharField(max_length=50, blank=True, default='')
    content = models.TextField(blank=True, default='')
    is_published = models.BooleanField(default=True)

    class Meta:
        db_table = 'reviews'
        ordering = ('-created_at',)
        unique_together = ('user', 'product')
        indexes = [
            models.Index(fields=['product']),
            models.Index(fields=['user']),
            models.Index(fields=['star']),
            models.Index(fields=['is_published']),
        ]

    def __str__(self):
        return f'{self.product.product_name} - {self.star}★ by {self.user.email}'


class ReviewImage(models.Model):
    review = models.ForeignKey(Review, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='reviews/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'review_images'
        ordering = ('id',)

    def __str__(self):
        return f'Image for review {self.review_id}'
