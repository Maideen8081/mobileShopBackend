import re
from django.contrib.auth import authenticate
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.utils import timezone
from rest_framework import serializers
from .models import Address, Customer

User = get_user_model()


class AddressSerializer(serializers.ModelSerializer):
    address_id = serializers.IntegerField(source='id', read_only=True)
    mobile = serializers.CharField(source='mobile_number')
    alternate_mobile = serializers.CharField(source='alternate_mobile_number', required=False, allow_blank=True)
    address_line1 = serializers.CharField(source='house_number')
    address_line2 = serializers.CharField(source='street_address', required=False, allow_blank=True)
    zip_code = serializers.CharField(source='pincode')

    class Meta:
        model = Address
        fields = [
            'address_id', 'full_name', 'mobile', 'alternate_mobile',
            'address_line1', 'address_line2', 'landmark', 'country', 'state',
            'city', 'zip_code', 'address_type', 'is_default',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']

    def validate_mobile(self, value):
        cleaned = re.sub(r'[\s\-\(\)]', '', value)
        if not re.match(r'^\+?\d{10,15}$', cleaned):
            raise serializers.ValidationError('Enter a valid mobile number (10-15 digits).')
        return value

    def validate_alternate_mobile(self, value):
        if not value:
            return value
        cleaned = re.sub(r'[\s\-\(\)]', '', value)
        if not re.match(r'^\+?\d{10,15}$', cleaned):
            raise serializers.ValidationError('Enter a valid alternate mobile number.')
        return value

    def validate_zip_code(self, value):
        if not re.match(r'^\d{5,10}$', value):
            raise serializers.ValidationError('Enter a valid zip code (5-10 digits).')
        return value


class AddressCreateSerializer(serializers.ModelSerializer):
    mobile = serializers.CharField(source='mobile_number', required=False)
    alternate_mobile = serializers.CharField(source='alternate_mobile_number', required=False, allow_blank=True)
    address_line1 = serializers.CharField(source='house_number', required=False)
    # Optional in the app's address forms (area / locality).
    address_line2 = serializers.CharField(source='street_address', required=False, allow_blank=True, default='')
    zip_code = serializers.CharField(source='pincode', required=False)

    class Meta:
        model = Address
        fields = [
            'full_name', 'mobile', 'alternate_mobile',
            'address_line1', 'address_line2', 'landmark', 'country', 'state',
            'city', 'zip_code', 'address_type', 'is_default',
            'delivery_instructions',
        ]

    def to_internal_value(self, data):
        normalized = dict(data)
        alias_map = {
            'mobile': 'mobile_number',
            'address_line1': 'house_number',
            'address_line2': 'street_address',
            'zip_code': 'pincode',
            'alternate_mobile': 'alternate_mobile_number',
        }
        for alias, original in alias_map.items():
            if alias not in normalized and original in normalized:
                normalized[alias] = normalized[original]
        return super().to_internal_value(normalized)


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    confirm_password = serializers.CharField(write_only=True, min_length=8)
    full_name = serializers.CharField(write_only=True, required=False)
    first_name = serializers.CharField(max_length=30, required=False)
    last_name = serializers.CharField(max_length=30, required=False)
    mobile = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = User
        fields = ['email', 'password', 'confirm_password', 'full_name', 'first_name', 'last_name', 'mobile']

    def validate_email(self, value):
        value = value.strip().lower()
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError('A user with this email already exists.')
        if not re.match(r'^[\w\.\-]+@[\w\-]+\.\w{2,4}$', value):
            raise serializers.ValidationError('Enter a valid email address.')
        return value

    def validate_mobile(self, value):
        if not value:
            return value
        cleaned = re.sub(r'[\s\-\(\)]', '', value)
        if not re.match(r'^\+?\d{10,15}$', cleaned):
            raise serializers.ValidationError('Enter a valid mobile number (10-15 digits).')
        return value

    def validate(self, attrs):
        if attrs['password'] != attrs.pop('confirm_password'):
            raise serializers.ValidationError({'confirm_password': 'Passwords do not match.'})

        full_name = attrs.pop('full_name', '')
        if full_name:
            parts = full_name.strip().split(None, 1)
            attrs.setdefault('first_name', parts[0] if parts else '')
            attrs.setdefault('last_name', parts[1] if len(parts) > 1 else '')

        attrs.setdefault('first_name', '')
        attrs.setdefault('last_name', '')

        return attrs

    def create(self, validated_data):
        mobile = validated_data.pop('mobile', '')
        password = validated_data.pop('password')
        # Role is always forced to customer — clients can never self-assign an
        # admin role through registration or any request body.
        user = User(**validated_data, role=User.ROLE_CUSTOMER)
        user.set_password(password)
        user.save()

        Customer.objects.get_or_create(user=user, defaults={'mobile': mobile})
        return user


class LoginSerializer(serializers.Serializer):
    email = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        from apps.common.security import account_is_locked, record_login_failure

        email = attrs.get('email', '').strip().lower()
        password = attrs.get('password')

        if not email:
            raise serializers.ValidationError('Email is required.')

        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            user = None

        # Generic errors: do not disclose whether an email exists.
        generic_error = 'Invalid email or password.'

        if user is not None:
            if account_is_locked(user):
                raise serializers.ValidationError(
                    'Account temporarily locked. Please try again later.'
                )
            if user.check_password(password) and user.is_active:
                attrs['user'] = user
                return attrs
            record_login_failure(user)
            if user.failed_login_attempts == 0 and user.locked_until:
                raise serializers.ValidationError(
                    'Account temporarily locked. Please try again later.'
                )

        raise serializers.ValidationError(generic_error)


class UserSerializer(serializers.ModelSerializer):
    customer_id = serializers.IntegerField(source='customer_profile.id', read_only=True)
    mobile = serializers.SerializerMethodField()
    date_of_birth = serializers.DateField(source='customer_profile.date_of_birth')
    gender = serializers.CharField(source='customer_profile.gender', required=False)
    address = serializers.CharField(source='customer_profile.address', required=False)
    city = serializers.CharField(source='customer_profile.city', required=False)
    state = serializers.CharField(source='customer_profile.state', required=False)
    pincode = serializers.CharField(source='customer_profile.pincode', required=False)
    loyalty_points = serializers.IntegerField(source='customer_profile.loyalty_points', read_only=True)
    role = serializers.CharField(read_only=True)
    is_admin = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'customer_id', 'email', 'first_name', 'last_name',
            'mobile', 'date_of_birth', 'gender', 'address', 'city', 'state',
            'pincode', 'loyalty_points', 'is_active', 'date_joined',
            'role', 'is_admin',
        ]
        read_only_fields = ['id', 'is_active', 'date_joined', 'loyalty_points', 'role', 'is_admin']

    def get_mobile(self, obj):
        mobile = obj.mobile_number
        if not mobile:
            try:
                mobile = obj.customer_profile.mobile
            except Exception:
                mobile = ''
        return mobile

    def get_is_admin(self, obj):
        return bool(obj.is_admin)

    def update(self, instance, validated_data):
        # Role/privilege escalation is impossible through the profile endpoint;
        # ``role`` and ``is_admin`` are read-only and never land in validated_data.
        validated_data.pop('role', None)
        customer_data = validated_data.pop('customer_profile', {})
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if customer_data:
            customer, _ = Customer.objects.get_or_create(user=instance)
            for attr, value in customer_data.items():
                setattr(customer, attr, value)
            customer.save()

        return instance


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, min_length=8)
    confirm_password = serializers.CharField(required=True, min_length=8)

    def validate_old_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError('Current password is incorrect.')
        return value

    def validate(self, attrs):
        if attrs['new_password'] != attrs['confirm_password']:
            raise serializers.ValidationError({'confirm_password': 'New passwords do not match.'})
        if attrs['old_password'] == attrs['new_password']:
            raise serializers.ValidationError({'new_password': 'New password cannot be the same as current password.'})
        return attrs


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        return value.strip().lower()


class PasswordResetConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(min_length=8, write_only=True)
    confirm_password = serializers.CharField(min_length=8, write_only=True)

    def validate(self, attrs):
        from django.utils.http import urlsafe_base64_decode
        from apps.common.models import PasswordResetToken

        if attrs['new_password'] != attrs['confirm_password']:
            raise serializers.ValidationError({'confirm_password': 'Passwords do not match.'})

        try:
            uid = urlsafe_base64_decode(attrs['uid']).decode()
            user = User.objects.get(pk=uid, is_active=True)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist, UnicodeDecodeError):
            raise serializers.ValidationError('The reset link is invalid or has expired.')

        if not default_token_generator.check_token(user, attrs['token']):
            raise serializers.ValidationError('The reset link is invalid or has expired.')

        reset = PasswordResetToken.objects.filter(
            user=user,
            token_hash=PasswordResetToken.make_hash(attrs['token']),
            used_at__isnull=True,
            expires_at__gt=timezone.now(),
        ).order_by('-created_at').first()
        if reset is None:
            raise serializers.ValidationError('The reset link has already been used or has expired.')

        attrs['user'] = user
        attrs['reset'] = reset
        return attrs
