from django.contrib import admin
from django.utils.html import format_html

from apps.repairs.models import (
    Notification,
    RepairNote,
    RepairService,
    RepairStatusHistory,
    RepairTicket,
    RepairTicketPhoto,
)


@admin.register(RepairService)
class RepairServiceAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'icon', 'is_active', 'created_at']
    list_filter = ['is_active']
    search_fields = ['name', 'description']
    prepopulated_fields = {'slug': ('name',)}


class RepairTicketPhotoInline(admin.TabularInline):
    model = RepairTicketPhoto
    extra = 1
    readonly_fields = ['uploaded_at', 'image_preview']

    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" width="100" height="100" style="object-fit:cover;" />',
                obj.image.url,
            )
        return '-'
    image_preview.short_description = 'Preview'


class RepairStatusHistoryInline(admin.TabularInline):
    model = RepairStatusHistory
    extra = 0
    readonly_fields = ['status', 'updated_by', 'notes', 'created_at']
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


class RepairNoteInline(admin.TabularInline):
    model = RepairNote
    extra = 1
    fields = ['message', 'author_name', 'is_admin']


@admin.register(RepairTicket)
class RepairTicketAdmin(admin.ModelAdmin):
    list_display = [
        'ticket_number', 'source_badge', 'customer_name', 'mobile_number',
        'device_brand', 'device_model', 'issue_category',
        'priority', 'assigned_technician', 'status_colored', 'created_at',
    ]
    list_filter = [
        'status', 'source', 'priority', 'issue_category',
        'warranty_status',
    ]
    search_fields = [
        'ticket_number', 'customer_name', 'mobile_number',
        'device_brand', 'device_model', 'imei_number', 'email',
    ]
    readonly_fields = ['ticket_number', 'source', 'created_at', 'updated_at']
    inlines = [RepairTicketPhotoInline, RepairStatusHistoryInline, RepairNoteInline]
    ordering = ('-created_at',)

    fieldsets = (
        ('Ticket Info', {
            'fields': ('ticket_number', 'source', 'status', 'priority', 'assigned_technician', 'service'),
        }),
        ('Customer Details', {
            'fields': ('customer_name', 'mobile_number', 'alternate_number', 'email', 'address'),
        }),
        ('Device Details', {
            'fields': (
                'device_brand', 'device_model',
                'imei_number', 'serial_number', 'device_color', 'warranty_status',
            ),
        }),
        ('Issue Details', {
            'fields': ('issue_category', 'problem_description'),
        }),
        ('Local Shop Details', {
            'classes': ('collapse',),
            'fields': ('accessories_submitted', 'device_password', 'estimated_cost', 'estimated_completion_days'),
        }),
        ('Courier Details (Online)', {
            'classes': ('collapse',),
            'fields': ('courier_company', 'courier_tracking_number', 'courier_pickup_date', 'courier_expected_delivery_date'),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
        }),
    )

    def source_badge(self, obj):
        colors = {'online': 'blue', 'local': 'green'}
        color = colors.get(obj.source, 'gray')
        return format_html(
            '<span style="color:white;background:{};padding:2px 8px;border-radius:3px;font-size:11px;">{}</span>',
            color,
            obj.get_source_display(),
        )
    source_badge.short_description = 'Source'

    def status_colored(self, obj):
        colors = {
            'pending': 'gray',
            'device_received': 'blue',
            'inspection': 'orange',
            'waiting_parts': 'amber',
            'repair_in_progress': 'purple',
            'quality_check': 'indigo',
            'ready_for_pickup': 'teal',
            'shipped': 'cyan',
            'completed': 'green',
            'cancelled': 'red',
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="color:white;background:{};padding:3px 8px;border-radius:3px;font-weight:bold;">{}</span>',
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
            return format_html(
                '<img src="{}" width="80" height="80" style="object-fit:cover;" />',
                obj.image.url,
            )
        return '-'
    image_preview.short_description = 'Preview'


@admin.register(RepairStatusHistory)
class RepairStatusHistoryAdmin(admin.ModelAdmin):
    list_display = ['repair_ticket', 'status', 'updated_by', 'notes', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['repair_ticket__ticket_number', 'updated_by']
    readonly_fields = ['created_at']


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['title', 'user', 'notification_type', 'is_read', 'sent_at', 'created_at']
    list_filter = ['notification_type', 'is_read', 'created_at']
    search_fields = ['title', 'user__email', 'repair_ticket__ticket_number']
    readonly_fields = ['sent_at', 'created_at']
