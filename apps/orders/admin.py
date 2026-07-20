from django.contrib import admin
from .models import Coupon, Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ['product', 'variant', 'product_name', 'quantity', 'price', 'total_price']


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = ['code', 'discount_type', 'discount_value', 'minimum_amount', 'used_count', 'max_uses', 'expiry_date', 'is_active']
    list_filter = ['discount_type', 'is_active']
    search_fields = ['code']


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['order_number', 'user', 'payment_status', 'order_status', 'grand_total', 'created_at']
    list_filter = ['payment_status', 'order_status']
    search_fields = ['order_number', 'user__email']
    list_select_related = ['user']
    readonly_fields = ['order_number', 'razorpay_order_id', 'razorpay_payment_id', 'razorpay_signature']
    inlines = [OrderItemInline]


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ['id', 'order', 'product_name', 'quantity', 'price', 'total_price']
    list_select_related = ['order']
