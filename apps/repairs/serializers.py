import re

from rest_framework import serializers

from apps.common.serializers import get_absolute_image_url
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
            if not re.match(r'^\d{15}$', str(mutable['imei_number'])):
                mutable['imei_number'] = ''

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


class RepairTicketCreateSerializer(serializers.ModelSerializer):
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
            if not re.match(r'^\d{15}$', str(mutable['imei_number'])):
                mutable['imei_number'] = ''

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
            'photo_count', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'ticket_number', 'created_at', 'updated_at']

    def get_photo_count(self, obj):
        return obj.photos.count()

    def get_status_label(self, obj):
        return STATUS_LABELS.get(obj.status, obj.status)


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
            'status', 'status_label',
            'photos', 'notes', 'status_history',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'ticket_number', 'created_at', 'updated_at']

    def get_status_label(self, obj):
        return STATUS_LABELS.get(obj.status, obj.status)


class RepairTicketUpdateSerializer(serializers.ModelSerializer):
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
            if not re.match(r'^\d{15}$', str(mutable['imei_number'])):
                mutable['imei_number'] = ''

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
    notes = serializers.CharField(required=False, default='')
    updated_by = serializers.CharField(required=False, default='Admin')


class RepairTicketTechnicianSerializer(serializers.Serializer):
    assigned_technician = serializers.CharField(max_length=100)
