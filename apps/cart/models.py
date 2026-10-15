from decimal import Decimal

from django.db import models
from django.conf import settings
from apps.common.models import TimeStampedModel
from apps.common.pricing import shipping_for, tax_for
from apps.products.models import Product, ProductVariant, VariantImage


class Cart(TimeStampedModel):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='cart')

    class Meta:
        db_table = 'carts'

    def __str__(self):
        return f'Cart - {self.user.email}'

    @property
    def subtotal(self):
        return sum(item.total_price for item in self.items.all())

    @property
    def discount(self):
        return sum(item.discount_amount for item in self.items.all())

    @property
    def payable_subtotal(self):
        """Subtotal after product discounts — what tax and shipping apply to."""
        return self.subtotal - self.discount

    @property
    def tax(self):
        return tax_for(self.payable_subtotal)

    @property
    def shipping_charge(self):
        return shipping_for(self.payable_subtotal)

    @property
    def grand_total(self):
        return self.payable_subtotal + self.tax + self.shipping_charge

    @property
    def total_quantity(self):
        return sum(item.quantity for item in self.items.all())


class CartItem(TimeStampedModel):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    variant = models.ForeignKey(ProductVariant, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    discount_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    class Meta:
        db_table = 'cart_items'
        unique_together = ('cart', 'variant')

    def __str__(self):
        return f'{self.product.product_name} ({self.variant.variant_name}) x {self.quantity}'

    @property
    def total_price(self):
        return self.price * self.quantity

    @property
    def discount_amount(self):
        if self.discount_price:
            return (self.price - self.discount_price) * self.quantity
        return 0

    @property
    def stock_status(self):
        if self.variant.stock_quantity == 0:
            return 'out_of_stock'
        if self.variant.stock_quantity <= self.variant.low_stock_alert:
            return 'low_stock'
        return 'in_stock'
