from django.contrib import admin
from .models import Customer, Address


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('user', 'mobile', 'loyalty_points', 'total_purchases', 'city', 'created_at')
    search_fields = ('user__email', 'user__first_name', 'user__last_name', 'mobile', 'city')


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'full_name', 'city', 'state', 'pincode', 'address_type', 'is_default', 'created_at')
    list_filter = ('address_type', 'is_default', 'state', 'city')
    search_fields = ('full_name', 'mobile_number', 'city', 'state', 'pincode', 'house_number', 'street_address')
    list_select_related = ('user',)
