import re

from rest_framework import serializers

from apps.common.serializers import AbsoluteImageField
from apps.repairs.constants import FIELD_ALIASES
from apps.repairs.models import RepairNote, RepairTicket, RepairTicketPhoto


class RepairTicketPhotoSerializer(serializers.ModelSerializer):
    image = AbsoluteImageField()

    class Meta:
        model = RepairTicketPhoto
        fields = ['id', 'image', 'uploaded_at']
        read_only_fields = ['id', 'uploaded_at']


class RepairNoteCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = RepairNote
        fields = ['message', 'author_name', 'is_admin']

    def create(self, validated_data):
        ticket_id = self.context.get('ticket_id')
        note = RepairNote.objects.create(
            repair_ticket_id=ticket_id,
            **validated_data,
        )
        return note


class RepairNoteListSerializer(serializers.ModelSerializer):
    class Meta:
        model = RepairNote
        fields = ['id', 'message', 'author_name', 'is_admin', 'created_at']


class RepairTicketListSerializer(serializers.ModelSerializer):
    photo_count = serializers.SerializerMethodField()

    class Meta:
        model = RepairTicket
        fields = [
            'id', 'ticket_number', 'customer_name', 'mobile_number',
            'device_category', 'device_brand', 'device_model',
            'issue_category', 'problem_description', 'priority',
            'estimated_cost', 'estimated_completion_days',
            'assigned_technician', 'status', 'photo_count',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'ticket_number', 'created_at', 'updated_at']

    def get_photo_count(self, obj):
        return obj.photos.count()


class RepairTicketDetailSerializer(serializers.ModelSerializer):
    photos = RepairTicketPhotoSerializer(many=True, read_only=True)
    notes = RepairNoteListSerializer(many=True, read_only=True)

    class Meta:
        model = RepairTicket
        fields = [
            'id', 'ticket_number',
            'customer_name', 'mobile_number', 'alternate_number',
            'email', 'address',
            'device_category', 'device_brand', 'device_model',
            'imei_number', 'serial_number', 'device_color', 'warranty_status',
            'issue_category', 'problem_description', 'priority',
            'accessories_submitted', 'device_password',
            'estimated_cost', 'estimated_completion_days',
            'assigned_technician', 'customer_approval_required',
            'status', 'photos', 'notes', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'ticket_number', 'created_at', 'updated_at']


class RepairTicketCreateSerializer(serializers.ModelSerializer):
    photos = serializers.ListField(
        child=serializers.ImageField(),
        write_only=True,
        required=False,
    )

    class Meta:
        model = RepairTicket
        fields = [
            'customer_name', 'mobile_number', 'alternate_number',
            'email', 'address',
            'device_category', 'device_brand', 'device_model',
            'imei_number', 'serial_number', 'device_color', 'warranty_status',
            'issue_category', 'problem_description', 'priority',
            'accessories_submitted', 'device_password',
            'estimated_cost', 'estimated_completion_days',
            'assigned_technician', 'customer_approval_required',
            'status', 'photos',
        ]

    def to_internal_value(self, data):
        photos = []
        if hasattr(data, 'getlist'):
            photos = data.getlist('photos')

        mutable = {}
        for key in data.keys():
            mutable[key] = data[key]

        data = mutable

        for frontend_field, backend_field in FIELD_ALIASES.items():
            if frontend_field in data and backend_field not in data:
                data[backend_field] = data.pop(frontend_field)

        for num_field in ['mobile_number', 'alternate_number']:
            if num_field in data and data[num_field]:
                cleaned = re.sub(r'\D', '', str(data[num_field]))
                data[num_field] = cleaned

        if 'imei_number' in data and data['imei_number']:
            if not re.match(r'^\d{15}$', str(data['imei_number'])):
                data['imei_number'] = ''

        if photos:
            data['photos'] = photos

        return super().to_internal_value(data)

    def validate_mobile_number(self, value):
        from apps.repairs.validators import validate_mobile_number
        from django.core.exceptions import ValidationError as DjangoValidationError
        try:
            validate_mobile_number(value)
        except DjangoValidationError as e:
            raise serializers.ValidationError(e.message)
        return value

    def validate_estimated_cost(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError('Estimated cost cannot be negative.')
        return value

    def validate_estimated_completion_days(self, value):
        if value is not None and value < 1:
            raise serializers.ValidationError('Estimated completion days must be at least 1.')
        return value

    def create(self, validated_data):
        photos_data = validated_data.pop('photos', [])
        ticket = RepairTicket.objects.create(**validated_data)

        from apps.repairs.services import RepairTicketService
        RepairTicketService.create_photos(ticket, photos_data)

        return ticket


class RepairTicketUpdateSerializer(serializers.ModelSerializer):
    photos = serializers.ListField(
        child=serializers.ImageField(),
        write_only=True,
        required=False,
    )
    delete_photo_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False,
    )

    class Meta:
        model = RepairTicket
        fields = [
            'customer_name', 'mobile_number', 'alternate_number',
            'email', 'address',
            'device_category', 'device_brand', 'device_model',
            'imei_number', 'serial_number', 'device_color', 'warranty_status',
            'issue_category', 'problem_description', 'priority',
            'accessories_submitted', 'device_password',
            'estimated_cost', 'estimated_completion_days',
            'assigned_technician', 'customer_approval_required',
            'status', 'photos', 'delete_photo_ids',
        ]
        extra_kwargs = {f: {'required': False} for f in [
            'customer_name', 'mobile_number', 'device_category',
            'device_brand', 'device_model', 'issue_category', 'problem_description',
        ]}

    def to_internal_value(self, data):
        photos = []
        if hasattr(data, 'getlist'):
            photos = data.getlist('photos')

        mutable = {}
        for key in data.keys():
            mutable[key] = data[key]

        data = mutable

        for frontend_field, backend_field in FIELD_ALIASES.items():
            if frontend_field in data and backend_field not in data:
                data[backend_field] = data.pop(frontend_field)

        for num_field in ['mobile_number', 'alternate_number']:
            if num_field in data and data[num_field]:
                cleaned = re.sub(r'\D', '', str(data[num_field]))
                data[num_field] = cleaned

        if 'imei_number' in data and data['imei_number']:
            if not re.match(r'^\d{15}$', str(data['imei_number'])):
                data['imei_number'] = ''

        if photos:
            data['photos'] = photos

        return super().to_internal_value(data)

    def validate_mobile_number(self, value):
        from apps.repairs.validators import validate_mobile_number
        from django.core.exceptions import ValidationError as DjangoValidationError
        try:
            validate_mobile_number(value)
        except DjangoValidationError as e:
            raise serializers.ValidationError(e.message)
        return value

    def validate_estimated_cost(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError('Estimated cost cannot be negative.')
        return value

    def validate_estimated_completion_days(self, value):
        if value is not None and value < 1:
            raise serializers.ValidationError('Estimated completion days must be at least 1.')
        return value

    def update(self, instance, validated_data):
        photos_data = validated_data.pop('photos', [])
        delete_ids = validated_data.pop('delete_photo_ids', [])

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if delete_ids:
            RepairTicketPhoto.objects.filter(
                id__in=delete_ids,
                repair_ticket=instance,
            ).delete()

        if photos_data:
            from apps.repairs.services import RepairTicketService
            RepairTicketService.create_photos(instance, photos_data)

        return instance


class RepairTicketStatusSerializer(serializers.Serializer):
    status = serializers.CharField(max_length=30)

    def to_internal_value(self, data):
        mutable = {}
        for key in data.keys():
            mutable[key] = data[key]
        return super().to_internal_value(mutable)


class RepairTicketTechnicianSerializer(serializers.Serializer):
    assigned_technician = serializers.CharField(max_length=100)
