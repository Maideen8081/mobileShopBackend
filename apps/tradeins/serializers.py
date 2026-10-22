from rest_framework import serializers

from apps.common.validators import (
    clean_amount, clean_indian_mobile, clean_person_name, clean_required_text,
)

from .models import TradeIn

STORAGE_OPTIONS = {'64GB', '128GB', '256GB', '512GB', '1TB'}


class TradeInSerializer(serializers.ModelSerializer):
    trade_id = serializers.CharField(read_only=True)
    status_label = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = TradeIn
        fields = [
            'id', 'trade_id', 'user',
            'customer_name', 'customer_mobile', 'customer_email',
            'device_brand', 'device_model', 'device_storage', 'device_condition',
            'estimated_value', 'quoted_price', 'final_value',
            'status', 'status_label', 'admin_notes', 'rejection_reason',
            'payment_method', 'payment_status',
            'created_at', 'updated_at',
        ]
        read_only_fields = fields


class TradeInCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = TradeIn
        fields = [
            'customer_name', 'customer_mobile', 'customer_email',
            'device_brand', 'device_model', 'device_storage', 'device_condition',
            'estimated_value',
        ]
        extra_kwargs = {
            'customer_email': {'required': False, 'allow_blank': True},
            'device_storage': {'required': False, 'allow_blank': True},
            'estimated_value': {'required': False},
        }

    def validate_customer_name(self, value):
        return clean_person_name(value, 'Full name')

    def validate_customer_mobile(self, value):
        return clean_indian_mobile(value)

    def validate_customer_email(self, value):
        return (value or '').strip().lower()

    def validate_device_brand(self, value):
        return clean_required_text(value, 'Device brand', max_len=50)

    def validate_device_model(self, value):
        return clean_required_text(value, 'Device model', min_len=2, max_len=100)

    def validate_device_storage(self, value):
        value = (value or '').strip().upper()
        if value and value not in STORAGE_OPTIONS:
            raise serializers.ValidationError(f'Storage must be one of: {", ".join(sorted(STORAGE_OPTIONS))}.')
        return value

    def validate_estimated_value(self, value):
        return clean_amount(value, 'Estimated value', allow_zero=True)


class TradeInAdminUpdateSerializer(serializers.ModelSerializer):
    """Free edits from the admin edit dialog. Status changes go through the
    dedicated workflow endpoints so transitions are always checked."""

    class Meta:
        model = TradeIn
        fields = ['admin_notes', 'final_value', 'quoted_price', 'payment_method']
        extra_kwargs = {f: {'required': False} for f in fields}

    def validate_admin_notes(self, value):
        value = (value or '').strip()
        if len(value) > 2000:
            raise serializers.ValidationError('Notes must be at most 2000 characters.')
        return value

    def validate_final_value(self, value):
        return None if value is None else clean_amount(value, 'Final value')

    def validate_quoted_price(self, value):
        return None if value is None else clean_amount(value, 'Quoted price')


class TradeInStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=TradeIn.STATUS_CHOICES)
    notes = serializers.CharField(required=False, allow_blank=True, max_length=2000)


class TradeInQuoteSerializer(serializers.Serializer):
    quoted_price = serializers.DecimalField(max_digits=10, decimal_places=2)
    notes = serializers.CharField(required=False, allow_blank=True, max_length=2000)

    def validate_quoted_price(self, value):
        return clean_amount(value, 'Quoted price')


class TradeInAcceptSerializer(serializers.Serializer):
    final_value = serializers.DecimalField(max_digits=10, decimal_places=2)
    notes = serializers.CharField(required=False, allow_blank=True, max_length=2000)

    def validate_final_value(self, value):
        return clean_amount(value, 'Final value')


class TradeInRejectSerializer(serializers.Serializer):
    rejection_reason = serializers.CharField(max_length=1000)

    def validate_rejection_reason(self, value):
        return clean_required_text(value, 'Rejection reason', min_len=5, max_len=1000)


class TradeInPaySerializer(serializers.Serializer):
    payment_method = serializers.ChoiceField(choices=TradeIn.PAYMENT_METHOD_CHOICES)
    notes = serializers.CharField(required=False, allow_blank=True, max_length=2000)
