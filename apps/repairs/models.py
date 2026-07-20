from django.db import models

from apps.common.models import TimeStampedModel
from apps.repairs.validators import (
    validate_completion_days,
    validate_estimated_cost,
    validate_imei_number,
    validate_mobile_number,
)
from apps.repairs.utils import generate_ticket_number


class RepairTicket(TimeStampedModel):
    ticket_number = models.CharField(max_length=20, unique=True, editable=False)
    customer_name = models.CharField(max_length=100)
    mobile_number = models.CharField(max_length=15, validators=[validate_mobile_number])
    alternate_number = models.CharField(max_length=15, blank=True, default='')
    email = models.EmailField(blank=True, default='')
    address = models.TextField(blank=True, default='')

    device_category = models.CharField(max_length=30)
    device_brand = models.CharField(max_length=100)
    device_model = models.CharField(max_length=100)
    imei_number = models.CharField(max_length=15, blank=True, default='', validators=[validate_imei_number])
    serial_number = models.CharField(max_length=100, blank=True, default='')
    device_color = models.CharField(max_length=50, blank=True, default='')
    warranty_status = models.CharField(max_length=20, default='unknown')

    issue_category = models.CharField(max_length=50)
    problem_description = models.TextField()
    priority = models.CharField(max_length=20, default='medium')
    accessories_submitted = models.TextField(blank=True, default='')
    device_password = models.CharField(max_length=100, blank=True, default='')

    estimated_cost = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, validators=[validate_estimated_cost])
    estimated_completion_days = models.IntegerField(null=True, blank=True, validators=[validate_completion_days])

    assigned_technician = models.CharField(max_length=100, blank=True, default='')
    customer_approval_required = models.BooleanField(default=True)

    status = models.CharField(max_length=30, default='pending')

    class Meta:
        db_table = 'repair_tickets'
        ordering = ('-created_at',)
        indexes = [
            models.Index(fields=['ticket_number']),
            models.Index(fields=['status']),
            models.Index(fields=['device_category']),
            models.Index(fields=['priority']),
        ]

    def save(self, *args, **kwargs):
        if not self.ticket_number:
            self.ticket_number = generate_ticket_number()
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.ticket_number} - {self.customer_name} ({self.device_brand} {self.device_model})'


class RepairTicketPhoto(models.Model):
    repair_ticket = models.ForeignKey(RepairTicket, on_delete=models.CASCADE, related_name='photos')
    image = models.ImageField(upload_to='repairs/photos/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'repair_ticket_photos'
        ordering = ('uploaded_at',)

    def __str__(self):
        return f'Photo for {self.repair_ticket.ticket_number}'


class RepairNote(models.Model):
    repair_ticket = models.ForeignKey(RepairTicket, on_delete=models.CASCADE, related_name='notes')
    message = models.TextField()
    author_name = models.CharField(max_length=100, default='Customer')
    is_admin = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'repair_notes'
        ordering = ('created_at',)

    def __str__(self):
        return f'Note on {self.repair_ticket.ticket_number} by {"Admin" if self.is_admin else self.author_name}'
