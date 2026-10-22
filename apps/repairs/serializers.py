import re
from decimal import Decimal

from rest_framework import serializers

from apps.common.serializers import get_absolute_image_url
from apps.common.validators import clean_person_name, clean_required_text
from apps.repairs.constants import FIELD_ALIASES, STATUS_LABELS
from apps.repairs.models import (
    Notification,
    RepairNote,
    RepairService,
    RepairStatusHistory,
    RepairTicket,
    RepairTicketPhoto,
)


class RepairServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = RepairService
        fields = ['id', 'name', 'slug', 'description', 'icon', 'is_active']


class RepairTicketPhotoSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = RepairTicketPhoto
        fields = ['id', 'image_url', 'uploaded_at']
        read_only_fields = ['id', 'uploaded_at']

    def get_image_url(self, obj):
        if obj.image:
            return get_absolute_image_url(obj.image, self.context.get('request'))
        return None


class RepairStatusHistorySerializer(serializers.ModelSerializer):
    status_label = serializers.SerializerMethodField()

    class Meta:
        model = RepairStatusHistory
        fields = ['id', 'status', 'status_label', 'updated_by', 'notes', 'created_at']
        read_only_fields = ['id', 'created_at']

    def get_status_label(self, obj):
        return STATUS_LABELS.get(obj.status, obj.status)


class RepairNoteListSerializer(serializers.ModelSerializer):
    class Meta:
        model = RepairNote
        fields = ['id', 'message', 'author_name', 'is_admin', 'created_at']


class RepairNoteCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = RepairNote
        fields = ['message', 'author_name', 'is_admin']

    def create(self, validated_data):
        ticket_id = self.context.get('ticket_id')
        return RepairNote.objects.create(repair_ticket_id=ticket_id, **validated_data)


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = [
            'id', 'title', 'message', 'notification_type',
            'is_read', 'sent_at', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class RepairBookSerializer(serializers.Serializer):
    service_id = serializers.IntegerField(required=False, allow_null=True)
    customer_name = serializers.CharField(max_length=100)
    mobile_number = serializers.CharField(max_length=15)
    alternate_number = serializers.CharField(max_length=15, required=False, default='')
    email = serializers.EmailField(required=True)
    address = serializers.CharField(required=False, default='')
    device_brand = serializers.CharField(max_length=100)
    device_model = serializers.CharField(max_length=100)
    imei_number = serializers.CharField(max_length=15, required=False, default='')
    serial_number = serializers.CharField(max_length=100, required=False, default='')
    device_color = serializers.CharField(max_length=50, required=False, default='')
    warranty_status = serializers.CharField(max_length=20, required=False, default='unknown')
    issue_category = serializers.CharField(max_length=50)
    problem_description = serializers.CharField()
    courier_company = serializers.CharField(max_length=100, required=False, default='')
    courier_tracking_number = serializers.CharField(max_length=100, required=False, default='')
    courier_pickup_date = serializers.DateField(required=False, allow_null=True)
    courier_expected_delivery_date = serializers.DateField(required=False, allow_null=True)

    def to_internal_value(self, data):
        mutable = {key: data[key] for key in data.keys()}

        for frontend_field, backend_field in FIELD_ALIASES.items():
            if frontend_field in mutable and backend_field not in mutable:
                mutable[backend_field] = mutable.pop(frontend_field)

        for num_field in ['mobile_number', 'alternate_number']:
            if num_field in mutable and mutable[num_field]:
                mutable[num_field] = re.sub(r'\D', '', str(mutable[num_field]))

        if 'imei_number' in mutable and mutable['imei_number']:
            # Accept "35 209 ... " or dashed input, but never silently drop a
            # wrong IMEI: validate_imei_number reports it to the user.
            mutable['imei_number'] = re.sub(r'[\s-]', '', str(mutable['imei_number']))

        return super().to_internal_value(mutable)

    def validate(self, data):
        service_id = data.get('service_id')
        issue_category = data.get('issue_category', '')

        if service_id:
            try:
                data['service'] = RepairService.objects.get(id=service_id, is_active=True)
            except RepairService.DoesNotExist:
                raise serializers.ValidationError({'service_id': 'Repair service not found or inactive.'})
        else:
            data['service'] = RepairService.objects.filter(
                name__iexact=issue_category, is_active=True
            ).first()

        return data

    def validate_mobile_number(self, value):
        cleaned = re.sub(r'\D', '', str(value))
        if len(cleaned) < 10 or len(cleaned) > 15:
            raise serializers.ValidationError('Mobile number must be 10-15 digits.')
        return cleaned

    def validate_imei_number(self, value):
        if value and not re.match(r'^\d{15}$', str(value)):
            return ''
        return value


class AdminTicketValidationMixin:
    """Field rules shared by the admin create and edit forms."""

    def validate_customer_name(self, value):
        return clean_person_name(value, 'Customer name')

    def validate_alternate_number(self, value):
        value = re.sub(r'\D', '', str(value or ''))
        if value and not re.match(r'^\d{10,15}$', value):
            raise serializers.ValidationError('Alternate number must be 10-15 digits.')
        return value

    def validate_email(self, value):
        return (value or '').strip().lower()

    def validate_device_brand(self, value):
        return clean_required_text(value, 'Device brand', max_len=100)

    def validate_device_model(self, value):
        return clean_required_text(value, 'Device model', max_len=100)

    def validate_imei_number(self, value):
        if value and not re.match(r'^\d{15}$', str(value)):
            raise serializers.ValidationError('IMEI must be exactly 15 digits.')
        return value or ''

    def validate_issue_category(self, value):
        return clean_required_text(value, 'Issue category', max_len=50)

    def validate_problem_description(self, value):
        return clean_required_text(value, 'Problem description', min_len=10, max_len=2000)

    def validate_estimated_cost(self, value):
        if value is None:
            return value
        if value < 0:
            raise serializers.ValidationError('Estimated cost cannot be negative.')
        if value > Decimal('500000'):
            raise serializers.ValidationError('Estimated cost looks too high (max ₹5,00,000).')
        return value

    def validate_estimated_completion_days(self, value):
        if value is None:
            return value
        if value < 1 or value > 60:
            raise serializers.ValidationError('Completion time must be between 1 and 60 days.')
        return value

    def validate_repair_charge(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError('Repair charge cannot be negative.')
        return value

    def validate(self, attrs):
        attrs = super().validate(attrs)
        mobile = attrs.get('mobile_number') or getattr(self.instance, 'mobile_number', '')
        alternate = attrs.get('alternate_number')
        if alternate and mobile and alternate == mobile:
            raise serializers.ValidationError({'alternate_number': 'Alternate number must differ from the mobile number.'})
        return attrs


class RepairTicketCreateSerializer(AdminTicketValidationMixin, serializers.ModelSerializer):
    photos = serializers.ListField(
        child=serializers.ImageField(), write_only=True, required=False
    )

    class Meta:
        model = RepairTicket
        fields = [
            'customer_name', 'mobile_number', 'alternate_number',
            'email', 'address',
            'device_brand', 'device_model',
            'imei_number', 'serial_number', 'device_color', 'warranty_status',
            'issue_category', 'problem_description',
            'accessories_submitted', 'device_password',
            'estimated_cost', 'estimated_completion_days',
            'assigned_technician', 'priority',
            'photos',
        ]

    def to_internal_value(self, data):
        photos = []
        if hasattr(data, 'getlist'):
            photos = data.getlist('photos')

        mutable = {key: data[key] for key in data.keys()}

        for frontend_field, backend_field in FIELD_ALIASES.items():
            if frontend_field in mutable and backend_field not in mutable:
                mutable[backend_field] = mutable.pop(frontend_field)

        for num_field in ['mobile_number', 'alternate_number']:
            if num_field in mutable and mutable[num_field]:
                mutable[num_field] = re.sub(r'\D', '', str(mutable[num_field]))

        if 'imei_number' in mutable and mutable['imei_number']:
            # Accept "35 209 ... " or dashed input, but never silently drop a
            # wrong IMEI: validate_imei_number reports it to the user.
            mutable['imei_number'] = re.sub(r'[\s-]', '', str(mutable['imei_number']))

        if photos:
            mutable['photos'] = photos

        return super().to_internal_value(mutable)

    def validate_mobile_number(self, value):
        cleaned = re.sub(r'\D', '', str(value))
        if len(cleaned) < 10 or len(cleaned) > 15:
            raise serializers.ValidationError('Mobile number must be 10-15 digits.')
        return cleaned

    def create(self, validated_data):
        photos_data = validated_data.pop('photos', [])
        ticket = RepairTicket.objects.create(source='local', **validated_data)

        if photos_data:
            from apps.repairs.services import RepairTicketService
            RepairTicketService.create_photos(ticket, photos_data)

        return ticket


class RepairTicketListSerializer(serializers.ModelSerializer):
    photo_count = serializers.SerializerMethodField()
    status_label = serializers.SerializerMethodField()
    service_name = serializers.CharField(source='service.name', read_only=True, default='')

    class Meta:
        model = RepairTicket
        fields = [
            'id', 'ticket_number', 'source', 'service_name',
            'customer_name', 'mobile_number', 'email',
            'device_brand', 'device_model',
            'issue_category', 'problem_description',
            'priority', 'status', 'status_label',
            'assigned_technician', 'estimated_cost', 'estimated_completion_days',
            'repair_reason', 'repair_charge', 'customer_approved',
            'photo_count', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'ticket_number', 'created_at', 'updated_at']

    def get_photo_count(self, obj):
        return obj.photos.count()

    def get_status_label(self, obj):
        return STATUS_LABELS.get(obj.status, obj.status)


class RepairMyTicketListSerializer(RepairTicketListSerializer):
    """Customer-facing list row: adds a thumbnail, courier info and the latest update.

    Expects ``photos`` and ``status_history`` to be prefetched.
    """
    thumbnail = serializers.SerializerMethodField()
    last_update = serializers.SerializerMethodField()

    class Meta(RepairTicketListSerializer.Meta):
        fields = RepairTicketListSerializer.Meta.fields + [
            'imei_number', 'device_color',
            'courier_company', 'courier_tracking_number', 'courier_pickup_date',
            'thumbnail', 'last_update',
        ]

    def get_photo_count(self, obj):
        return len(obj.photos.all())

    def get_thumbnail(self, obj):
        photos = obj.photos.all()
        if not photos:
            return None
        return get_absolute_image_url(photos[0].image, self.context.get('request')) or None

    def get_last_update(self, obj):
        history = obj.status_history.all()
        if not history:
            return None
        latest = history[0]
        return {
            'status': latest.status,
            'status_label': STATUS_LABELS.get(latest.status, latest.status),
            'notes': latest.notes,
            'created_at': latest.created_at,
        }


class RepairCustomerNoteSerializer(serializers.Serializer):
    message = serializers.CharField(max_length=2000, trim_whitespace=True)


class RepairCustomerCourierSerializer(serializers.Serializer):
    courier_company = serializers.CharField(max_length=100, trim_whitespace=True)
    courier_tracking_number = serializers.CharField(max_length=100, trim_whitespace=True)
    courier_pickup_date = serializers.DateField(required=False, allow_null=True)
    notes = serializers.CharField(max_length=500, required=False, allow_blank=True, default='')


class RepairCustomerCancelSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=500, required=False, allow_blank=True, default='')


class RepairTicketDetailSerializer(serializers.ModelSerializer):
    photos = RepairTicketPhotoSerializer(many=True, read_only=True)
    notes = RepairNoteListSerializer(many=True, read_only=True)
    status_history = RepairStatusHistorySerializer(many=True, read_only=True)
    status_label = serializers.SerializerMethodField()
    service_name = serializers.CharField(source='service.name', read_only=True, default='')

    class Meta:
        model = RepairTicket
        fields = [
            'id', 'ticket_number', 'source', 'service_name',
            'customer_name', 'mobile_number', 'alternate_number',
            'email', 'address',
            'device_brand', 'device_model',
            'imei_number', 'serial_number', 'device_color', 'warranty_status',
            'issue_category', 'problem_description',
    'accessories_submitted', 'device_password',
    'estimated_cost', 'estimated_completion_days',
    'assigned_technician', 'priority',
    'courier_company', 'courier_tracking_number',
    'courier_pickup_date', 'courier_expected_delivery_date',
    'repair_reason', 'repair_charge', 'customer_approved',
    'status', 'status_label',
    'photos', 'notes', 'status_history',
    'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'ticket_number', 'created_at', 'updated_at']

    def get_status_label(self, obj):
        return STATUS_LABELS.get(obj.status, obj.status)


class RepairTicketUpdateSerializer(AdminTicketValidationMixin, serializers.ModelSerializer):
    photos = serializers.ListField(
        child=serializers.ImageField(), write_only=True, required=False
    )
    delete_photo_ids = serializers.ListField(
        child=serializers.IntegerField(), write_only=True, required=False
    )

    class Meta:
        model = RepairTicket
        fields = [
            'customer_name', 'mobile_number', 'alternate_number',
            'email', 'address',
            'device_brand', 'device_model',
            'imei_number', 'serial_number', 'device_color', 'warranty_status',
            'issue_category', 'problem_description',
            'accessories_submitted', 'device_password',
            'estimated_cost', 'estimated_completion_days',
            'assigned_technician', 'priority',
            'courier_company', 'courier_tracking_number',
            'courier_pickup_date', 'courier_expected_delivery_date',
            'repair_reason', 'repair_charge',
            'photos', 'delete_photo_ids',
        ]
        extra_kwargs = {f: {'required': False} for f in [
            'customer_name', 'mobile_number', 'device_brand', 'device_model',
            'issue_category', 'problem_description',
        ]}

    def to_internal_value(self, data):
        photos = []
        if hasattr(data, 'getlist'):
            photos = data.getlist('photos')

        mutable = {key: data[key] for key in data.keys()}

        for frontend_field, backend_field in FIELD_ALIASES.items():
            if frontend_field in mutable and backend_field not in mutable:
                mutable[backend_field] = mutable.pop(frontend_field)

        for num_field in ['mobile_number', 'alternate_number']:
            if num_field in mutable and mutable[num_field]:
                mutable[num_field] = re.sub(r'\D', '', str(mutable[num_field]))

        if 'imei_number' in mutable and mutable['imei_number']:
            # Accept "35 209 ... " or dashed input, but never silently drop a
            # wrong IMEI: validate_imei_number reports it to the user.
            mutable['imei_number'] = re.sub(r'[\s-]', '', str(mutable['imei_number']))

        if photos:
            mutable['photos'] = photos

        return super().to_internal_value(mutable)

    def validate_mobile_number(self, value):
        cleaned = re.sub(r'\D', '', str(value))
        if len(cleaned) < 10 or len(cleaned) > 15:
            raise serializers.ValidationError('Mobile number must be 10-15 digits.')
        return cleaned

    def update(self, instance, validated_data):
        photos_data = validated_data.pop('photos', [])
        delete_ids = validated_data.pop('delete_photo_ids', [])

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if delete_ids:
            RepairTicketPhoto.objects.filter(id__in=delete_ids, repair_ticket=instance).delete()

        if photos_data:
            from apps.repairs.services import RepairTicketService
            RepairTicketService.create_photos(instance, photos_data)

        return instance


class RepairStatusUpdateSerializer(serializers.Serializer):
    status = serializers.CharField(max_length=30)
    notes = serializers.CharField(required=False, default='', allow_blank=True, max_length=2000)
    updated_by = serializers.CharField(required=False, default='Admin', max_length=100)
    repair_reason = serializers.CharField(required=False, default='', allow_blank=True, max_length=1000)
    repair_charge = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, allow_null=True)

    def validate_status(self, value):
        value = (value or '').strip()
        valid = {key for key, _ in RepairTicket.STATUS_CHOICES} | {'received'}
        if value not in valid:
            raise serializers.ValidationError('Unknown repair status.')
        return value

    def validate_repair_charge(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError('Repair charge cannot be negative.')
        return value

    def validate(self, attrs):
        if attrs['status'] in ('rejected', 'cancelled') and not attrs.get('notes', '').strip():
            raise serializers.ValidationError({'notes': 'Give a reason when rejecting or cancelling a repair.'})
        return attrs


class RepairCustomerApproveSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=['approve', 'decline'])
    notes = serializers.CharField(required=False, default='')


class RepairTicketTechnicianSerializer(serializers.Serializer):
    assigned_technician = serializers.CharField(max_length=100)

    def validate_assigned_technician(self, value):
        return clean_required_text(value, 'Technician name', min_len=2, max_len=100)
