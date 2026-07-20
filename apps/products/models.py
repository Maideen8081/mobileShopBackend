from django.db import models
from apps.common.models import TimeStampedModel


class Product(TimeStampedModel):
    product_name = models.CharField(max_length=200)
    brand = models.CharField(max_length=100)
    model_number = models.CharField(max_length=100)
    category = models.ForeignKey('categories.Category', on_delete=models.CASCADE, related_name='products')
    sub_category = models.ForeignKey('categories.SubCategory', on_delete=models.CASCADE, related_name='products', null=True, blank=True)
    description = models.TextField(blank=True)
    common_image = models.ImageField(upload_to='products/', null=True, blank=True)
    is_trending = models.BooleanField(default=False)
    is_new_arrival = models.BooleanField(default=False)
    is_best_selling = models.BooleanField(default=False)
    is_featured = models.BooleanField(default=False)
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
            models.Index(fields=['is_published']),
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
        ordering = ('-created_at',)
        indexes = [
            models.Index(fields=['product']),
            models.Index(fields=['is_active']),
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
