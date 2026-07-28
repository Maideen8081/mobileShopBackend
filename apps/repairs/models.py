from django.conf import settings
from django.db import models

from apps.common.models import TimeStampedModel
from apps.repairs.utils import generate_ticket_number


class RepairService(TimeStampedModel):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    description = models.TextField()
    icon = models.CharField(max_length=50)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'repair_services'
        ordering = ('name',)

    def __str__(self):
        return self.name


class RepairTicket(TimeStampedModel):
    SOURCE_CHOICES = [('online', 'Online'), ('local', 'Local Shop')]
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('device_received', 'Device Received'),
        ('inspection', 'Inspection'),
        ('waiting_parts', 'Waiting for Parts'),
        ('repair_in_progress', 'Repair In Progress'),
        ('quality_check', 'Quality Check'),
        ('ready_for_pickup', 'Ready for Pickup'),
        ('shipped', 'Shipped'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]

    ticket_number = models.CharField(max_length=20, unique=True, editable=False)
    source = models.CharField(max_length=10, choices=SOURCE_CHOICES, default='online')
    service = models.ForeignKey(
        RepairService, on_delete=models.SET_NULL, null=True, blank=True, related_name='tickets'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='repair_tickets'
    )

    customer_name = models.CharField(max_length=100)
    mobile_number = models.CharField(max_length=15)
    alternate_number = models.CharField(max_length=15, blank=True, default='')
    email = models.EmailField(blank=True, default='')
    address = models.TextField(blank=True, default='')

    device_brand = models.CharField(max_length=100)
    device_model = models.CharField(max_length=100)
    imei_number = models.CharField(max_length=15, blank=True, default='')
    serial_number = models.CharField(max_length=100, blank=True, default='')
    device_color = models.CharField(max_length=50, blank=True, default='')
    warranty_status = models.CharField(max_length=20, default='unknown')

    issue_category = models.CharField(max_length=50)
    problem_description = models.TextField()

    accessories_submitted = models.TextField(blank=True, default='')
    device_password = models.CharField(max_length=100, blank=True, default='')
    estimated_cost = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    estimated_completion_days = models.IntegerField(null=True, blank=True)
    assigned_technician = models.CharField(max_length=100, blank=True, default='')
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='medium')

    courier_company = models.CharField(max_length=100, blank=True, default='')
    courier_tracking_number = models.CharField(max_length=100, blank=True, default='')
    courier_pickup_date = models.DateField(null=True, blank=True)
    courier_expected_delivery_date = models.DateField(null=True, blank=True)

    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='pending')

    class Meta:
        db_table = 'repair_tickets'
        ordering = ('-created_at',)
        indexes = [
            models.Index(fields=['ticket_number']),
            models.Index(fields=['status']),
            models.Index(fields=['source']),
            models.Index(fields=['priority']),
            models.Index(fields=['user']),
        ]

    def save(self, *args, **kwargs):
        if not self.ticket_number:
            self.ticket_number = generate_ticket_number()
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.ticket_number} - {self.customer_name} ({self.device_brand} {self.device_model})'


class RepairStatusHistory(TimeStampedModel):
    repair_ticket = models.ForeignKey(
        RepairTicket, on_delete=models.CASCADE, related_name='status_history'
    )
    status = models.CharField(max_length=30)
    updated_by = models.CharField(max_length=100, default='System')
    notes = models.TextField(blank=True, default='')

    class Meta:
        db_table = 'repair_status_history'
        ordering = ('-created_at',)

    def __str__(self):
        return f'{self.repair_ticket.ticket_number} → {self.status}'


class RepairTicketPhoto(models.Model):
    repair_ticket = models.ForeignKey(
        RepairTicket, on_delete=models.CASCADE, related_name='photos'
    )
    image = models.ImageField(upload_to='repairs/photos/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'repair_ticket_photos'
        ordering = ('uploaded_at',)

    def __str__(self):
        return f'Photo for {self.repair_ticket.ticket_number}'


class RepairNote(models.Model):
    repair_ticket = models.ForeignKey(
        RepairTicket, on_delete=models.CASCADE, related_name='notes'
    )
    message = models.TextField()
    author_name = models.CharField(max_length=100, default='Customer')
    is_admin = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'repair_notes'
        ordering = ('created_at',)

    def __str__(self):
        return f'Note on {self.repair_ticket.ticket_number} by {self.author_name}'


class Notification(TimeStampedModel):
    TYPE_CHOICES = [('email', 'Email'), ('sms', 'SMS'), ('push', 'Push')]
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications'
    )
    repair_ticket = models.ForeignKey(
        RepairTicket, on_delete=models.SET_NULL, null=True, blank=True, related_name='notifications'
    )
    title = models.CharField(max_length=200)
    message = models.TextField()
    notification_type = models.CharField(max_length=10, choices=TYPE_CHOICES, default='email')
    is_read = models.BooleanField(default=False)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'notifications'
        ordering = ('-created_at',)

    def __str__(self):
        return f'{self.title} → {self.user}'
