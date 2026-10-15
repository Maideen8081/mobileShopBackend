"""Checkout pricing rules shared by the cart and order endpoints.

The storefront shows the same numbers (see the frontend's cartLogic.ts), so
change both together.
"""
from decimal import Decimal, ROUND_HALF_UP

TAX_RATE = Decimal('0.18')                 # GST
FREE_SHIPPING_THRESHOLD = Decimal('500.00')
DELIVERY_CHARGE = Decimal('49.00')


def money(value):
    return Decimal(value).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def selling_price(variant):
    """What the customer pays per unit: the discount price when one is set."""
    if variant.discount_price and variant.discount_price > 0:
        return money(variant.discount_price)
    return money(variant.price)


def tax_for(amount):
    return money(Decimal(amount) * TAX_RATE)


def shipping_for(amount):
    if not amount or Decimal(amount) >= FREE_SHIPPING_THRESHOLD:
        return Decimal('0.00')
    return DELIVERY_CHARGE
