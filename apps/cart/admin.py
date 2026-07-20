from django.contrib import admin
from .models import Cart, CartItem


class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 0
    readonly_fields = ['product', 'variant', 'quantity', 'price', 'discount_price']


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'total_quantity', 'subtotal', 'grand_total', 'created_at']
    list_select_related = ['user']
    readonly_fields = ['subtotal', 'tax', 'shipping_charge', 'discount', 'grand_total', 'total_quantity']
    inlines = [CartItemInline]


@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ['id', 'cart', 'product', 'variant', 'quantity', 'price', 'total_price']
    list_select_related = ['cart__user', 'product', 'variant']
