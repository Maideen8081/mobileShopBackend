from django.contrib import admin

from .models import TradeIn


@admin.register(TradeIn)
class TradeInAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer_name', 'device_brand', 'device_model', 'status', 'final_value', 'created_at')
    list_filter = ('status', 'device_brand', 'payment_status')
    search_fields = ('customer_name', 'customer_mobile', 'customer_email', 'device_model')
