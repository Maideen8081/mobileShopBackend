from django.contrib import admin
from django.utils.html import format_html

from apps.repairs.models import RepairTicket, RepairTicketPhoto


class RepairTicketPhotoInline(admin.TabularInline):
    model = RepairTicketPhoto
    extra = 1
    readonly_fields = ['uploaded_at', 'image_preview']

    def image_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" width="100" height="100" style="object-fit:cover;" />', obj.image.url)
        return '-'
    image_preview.short_description = 'Preview'


@admin.register(RepairTicket)
class RepairTicketAdmin(admin.ModelAdmin):
    list_display = [
        'ticket_number', 'customer_name', 'mobile_number',
        'device_brand', 'device_model', 'device_category',
        'issue_category', 'priority', 'estimated_cost',
        'assigned_technician', 'status_colored', 'created_at',
    ]
    list_filter = [
        'status', 'device_category', 'issue_category',
        'priority', 'warranty_status',
    ]
    search_fields = [
        'ticket_number', 'customer_name', 'mobile_number',
        'device_brand', 'device_model', 'imei_number',
        'serial_number',
    ]
    readonly_fields = ['ticket_number', 'created_at', 'updated_at']
    inlines = [RepairTicketPhotoInline]
    ordering = ('-created_at',)

    fieldsets = (
        ('Ticket Info', {
            'fields': ('ticket_number', 'status', 'priority', 'assigned_technician'),
        }),
        ('Customer Details', {
            'fields': ('customer_name', 'mobile_number', 'alternate_number', 'email', 'address'),
        }),
        ('Device Details', {
            'fields': (
                'device_category', 'device_brand', 'device_model',
                'imei_number', 'serial_number', 'device_color', 'warranty_status',
            ),
        }),
        ('Issue Details', {
            'fields': (
                'issue_category', 'problem_description',
                'accessories_submitted', 'device_password',
            ),
        }),
        ('Estimation', {
            'fields': ('estimated_cost', 'estimated_completion_days', 'customer_approval_required'),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
        }),
    )

    def status_colored(self, obj):
        colors = {
            'pending': 'gray',
            'diagnosing': 'blue',
            'waiting_approval': 'orange',
            'in_progress': 'purple',
            'completed': 'green',
            'delivered': 'teal',
            'cancelled': 'red',
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="color: white; background: {}; padding: 3px 8px; border-radius: 3px; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display(),
        )
    status_colored.short_description = 'Status'


@admin.register(RepairTicketPhoto)
class RepairTicketPhotoAdmin(admin.ModelAdmin):
    list_display = ['id', 'repair_ticket', 'image_preview', 'uploaded_at']
    list_filter = ['uploaded_at']
    search_fields = ['repair_ticket__ticket_number', 'repair_ticket__customer_name']

    def image_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" width="80" height="80" style="object-fit:cover;" />', obj.image.url)
        return '-'
    image_preview.short_description = 'Preview'
