from django.db import models
from django.db.models import F, Q
from django.db.models.functions import Length, Lower
from django.db.models.lookups import GreaterThanOrEqual

from apps.common.models import TimeStampedModel
from .validators import (
    BRAND_MIN, LOW_STOCK_ALERT_MAX, MODEL_NUMBER_PATTERN, PRODUCT_NAME_MIN, STOCK_MAX,
)


class Product(TimeStampedModel):
    product_name = models.CharField(max_length=200)
    brand = models.CharField(max_length=100)
    model_number = models.CharField(max_length=100)
    # PROTECT: deleting a category or sub category must never silently delete its products.
    category = models.ForeignKey('categories.Category', on_delete=models.PROTECT, related_name='products')
    sub_category = models.ForeignKey('categories.SubCategory', on_delete=models.PROTECT, related_name='products', null=True, blank=True)
    description = models.TextField(blank=True)
    common_image = models.ImageField(upload_to='products/', null=True, blank=True)
    is_trending = models.BooleanField(default=False)
    is_new_arrival = models.BooleanField(default=False)
    is_best_selling = models.BooleanField(default=False)
    is_featured = models.BooleanField(default=False)
    is_refurbished = models.BooleanField(default=False)
    is_published = models.BooleanField(default=True)

    class Meta:
        db_table = 'products'
        ordering = ('-created_at',)
        indexes = [
            models.Index(fields=['category']),
            models.Index(fields=['sub_category']),
            models.Index(fields=['is_trending']),
            models.Index(fields=['is_new_arrival']),
            models.Index(fields=['is_best_selling']),
            models.Index(fields=['is_refurbished']),
            models.Index(fields=['is_published']),
        ]
        constraints = [
            models.UniqueConstraint(Lower('brand'), Lower('model_number'), name='product_brand_model_unique_ci'),
            models.CheckConstraint(
                condition=GreaterThanOrEqual(Length('product_name'), PRODUCT_NAME_MIN), name='product_name_min_length',
            ),
            models.CheckConstraint(condition=GreaterThanOrEqual(Length('brand'), BRAND_MIN), name='product_brand_min_length'),
            models.CheckConstraint(
                condition=Q(model_number__regex=MODEL_NUMBER_PATTERN.pattern), name='product_model_number_format',
            ),
        ]

    def __str__(self):
        return self.product_name


class ProductFeature(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='features')
    feature_text = models.CharField(max_length=255)

    class Meta:
        db_table = 'product_features'
        ordering = ('id',)

    def __str__(self):
        return self.feature_text


class CareInstruction(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='care_instructions')
    instruction_text = models.TextField()

    class Meta:
        db_table = 'care_instructions'
        ordering = ('id',)

    def __str__(self):
        return self.instruction_text


class ProductVariant(TimeStampedModel):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='variants')
    variant_name = models.CharField(max_length=100)
    color = models.CharField(max_length=50)
    ram_size = models.CharField(max_length=20)
    storage_size = models.CharField(max_length=20)
    battery_capacity = models.CharField(max_length=50, default='')
    processor = models.CharField(max_length=100, default='')
    display_size = models.CharField(max_length=50, default='')
    camera_details = models.CharField(max_length=255, default='')
    price = models.DecimalField(max_digits=10, decimal_places=2)
    discount_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    stock_quantity = models.PositiveIntegerField(default=0)
    low_stock_alert = models.PositiveIntegerField(default=5)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'product_variants'
        ordering = ('id',)  # the order the admin entered them
        indexes = [
            models.Index(fields=['product']),
            models.Index(fields=['is_active']),
        ]
        constraints = [
            models.CheckConstraint(condition=Q(price__gt=0), name='variant_price_positive'),
            models.CheckConstraint(
                condition=Q(discount_price__isnull=True) | (Q(discount_price__gt=0) & Q(discount_price__lt=F('price'))),
                name='variant_discount_below_price',
            ),
            models.CheckConstraint(condition=Q(stock_quantity__lte=STOCK_MAX), name='variant_stock_max'),
            models.CheckConstraint(condition=Q(low_stock_alert__lte=LOW_STOCK_ALERT_MAX), name='variant_low_stock_alert_max'),
        ]

    def __str__(self):
        return f'{self.product.product_name} - {self.variant_name} ({self.color})'


class VariantImage(models.Model):
    variant = models.ForeignKey(ProductVariant, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='products/variants/')
    is_main = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'variant_images'
        ordering = ('-is_main', 'id')

    def __str__(self):
        return f'{self.variant.variant_name} Image'


class StockNotification(models.Model):
    """A shopper's request to be emailed when an out-of-stock product/variant is restocked."""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='stock_notifications')
    # Null means "any variant of this product".
    variant = models.ForeignKey(
        ProductVariant, on_delete=models.CASCADE, related_name='stock_notifications', null=True, blank=True,
    )
    email = models.EmailField()
    created_at = models.DateTimeField(auto_now_add=True)
    notified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'stock_notifications'
        ordering = ('-created_at',)
        indexes = [models.Index(fields=['product', 'notified_at'])]
        constraints = [
            # One pending request per email per product/variant; once sent they may subscribe again.
            models.UniqueConstraint(
                Lower('email'), 'product', 'variant',
                condition=Q(notified_at__isnull=True), name='stock_notification_pending_unique',
            ),
        ]

    def __str__(self):
        return f'{self.email} → {self.variant or self.product}'
