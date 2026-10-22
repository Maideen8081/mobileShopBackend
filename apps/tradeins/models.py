from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.common.models import TimeStampedModel


class TradeIn(TimeStampedModel):
    STATUS_PENDING = 'pending'
    STATUS_REVIEWED = 'reviewed'
    STATUS_ACCEPTED = 'accepted'
    STATUS_REJECTED = 'rejected'
    STATUS_PAID = 'paid'
    STATUS_CANCELLED = 'cancelled'

    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_REVIEWED, 'Reviewed'),
        (STATUS_ACCEPTED, 'Accepted'),
        (STATUS_REJECTED, 'Rejected'),
        (STATUS_PAID, 'Paid'),
        (STATUS_CANCELLED, 'Cancelled'),
    ]

    # Allowed forward moves. Terminal states (paid/rejected/cancelled) have none.
    TRANSITIONS = {
        STATUS_PENDING: {STATUS_REVIEWED, STATUS_ACCEPTED, STATUS_REJECTED, STATUS_CANCELLED},
        STATUS_REVIEWED: {STATUS_ACCEPTED, STATUS_REJECTED, STATUS_CANCELLED},
        STATUS_ACCEPTED: {STATUS_PAID, STATUS_REJECTED, STATUS_CANCELLED},
        STATUS_PAID: set(),
        STATUS_REJECTED: set(),
        STATUS_CANCELLED: set(),
    }

    CONDITION_CHOICES = [
        ('Mint - Like New', 'Mint - Like New'),
        ('Good - Minor Scratches', 'Good - Minor Scratches'),
        ('Fair - Visible Wear', 'Fair - Visible Wear'),
        ('Broken - Damaged Screen/Body', 'Broken - Damaged Screen/Body'),
    ]

    PAYMENT_METHOD_CHOICES = [
        ('upi', 'UPI'),
        ('bank_transfer', 'Bank Transfer'),
        ('cash', 'Cash'),
        ('store_credit', 'Store Credit'),
    ]

    PAYMENT_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='trade_ins'
    )
    customer_name = models.CharField(max_length=100)
    customer_mobile = models.CharField(max_length=15)
    customer_email = models.EmailField(blank=True, default='')

    device_brand = models.CharField(max_length=50)
    device_model = models.CharField(max_length=100)
    device_storage = models.CharField(max_length=20, blank=True, default='')
    device_condition = models.CharField(max_length=40, choices=CONDITION_CHOICES)

    estimated_value = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    quoted_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    final_value = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    admin_notes = models.TextField(blank=True, default='')
    rejection_reason = models.TextField(blank=True, default='')

    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, blank=True, default='')
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending')

    class Meta:
        db_table = 'trade_ins'
        ordering = ('-created_at',)
        indexes = [models.Index(fields=['status'])]
        constraints = [
            models.CheckConstraint(condition=Q(estimated_value__gte=0), name='tradein_estimated_non_negative'),
            models.CheckConstraint(
                condition=Q(quoted_price__isnull=True) | Q(quoted_price__gt=0), name='tradein_quote_positive'
            ),
            models.CheckConstraint(
                condition=Q(final_value__isnull=True) | Q(final_value__gt=0), name='tradein_final_positive'
            ),
        ]

    def __str__(self):
        return f'{self.trade_id} — {self.device_brand} {self.device_model}'

    @property
    def trade_id(self):
        return f'TRD-{self.pk:06d}' if self.pk else ''

    def can_transition_to(self, new_status):
        return new_status in self.TRANSITIONS.get(self.status, set())
