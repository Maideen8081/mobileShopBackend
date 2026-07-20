from django.db import models
from apps.common.models import TimeStampedModel
from django.conf import settings


class Customer(TimeStampedModel):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='customer_profile')
    mobile = models.CharField(max_length=15, blank=True, default='')
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=10, choices=(('male', 'Male'), ('female', 'Female'), ('other', 'Other')), blank=True)
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    pincode = models.CharField(max_length=10, blank=True)
    loyalty_points = models.PositiveIntegerField(default=0)
    total_purchases = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    notes = models.TextField(blank=True)

    class Meta:
        db_table = 'customers'
        ordering = ('-created_at',)

    def __str__(self):
        return self.user.get_full_name() or self.user.email


class Address(TimeStampedModel):
    ADDRESS_TYPES = [
        ('Home', 'Home'),
        ('Office', 'Office'),
        ('Other', 'Other'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='addresses', null=True, blank=True)
    full_name = models.CharField(max_length=100)
    mobile_number = models.CharField(max_length=15)
    alternate_mobile_number = models.CharField(max_length=15, blank=True)
    house_number = models.CharField(max_length=100)
    street_address = models.CharField(max_length=255)
    landmark = models.CharField(max_length=255, blank=True)
    country = models.CharField(max_length=100, default='India')
    state = models.CharField(max_length=100)
    city = models.CharField(max_length=100)
    pincode = models.CharField(max_length=10)
    address_type = models.CharField(max_length=10, choices=ADDRESS_TYPES, default='Home')
    delivery_instructions = models.TextField(blank=True)
    is_default = models.BooleanField(default=False)

    class Meta:
        db_table = 'addresses'
        ordering = ('-is_default', '-created_at')

    def __str__(self):
        return f'{self.full_name} - {self.house_number}, {self.city}'
