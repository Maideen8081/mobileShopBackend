from django.conf import settings
from django.contrib.auth import get_user_model, login, logout
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.http import urlsafe_base64_encode
from django.middleware.csrf import get_token
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import status
from rest_framework.generics import GenericAPIView, ListAPIView, RetrieveUpdateAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from apps.common.models import PasswordResetToken
from apps.common.permissions import IsAdminUser, is_admin_account
from apps.common.security import (
    log_security_event,
    mark_credentials_changed,
    reset_login_failures,
    revoke_all_sessions_for_user,
)

from .models import Address
from .serializers import (
    AddressSerializer, AddressCreateSerializer,
    RegisterSerializer, LoginSerializer, UserSerializer,
    ChangePasswordSerializer,
    PasswordResetRequestSerializer, PasswordResetConfirmSerializer,
)

User = get_user_model()


def _envelope(success, message='', data=None, meta=None):
    payload = {'success': success, 'message': message}
    if data is not None:
        payload['data'] = data
    if meta is not None:
        payload.update(meta)
    return payload


class CSRFTokenAPIView(GenericAPIView):
    """Issue the CSRF cookie so the SPA can echo X-CSRFToken on unsafe requests."""

    authentication_classes = []
    permission_classes = [AllowAny]

    @method_decorator(ensure_csrf_cookie)
    def get(self, request, *args, **kwargs):
        # The SPA runs on a different site than the API, so it can't read this
        # cookie via document.cookie; return the token in the body as well.
        return Response(_envelope(True, 'CSRF cookie set.', data={'csrf_token': get_token(request)}))


class RegisterAPIView(GenericAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'register'

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        # Annotate the session so the requester is authenticated immediately.
        login(request, user)
        log_security_event(request, 'auth.register', actor=user, target_type='user', target_id=str(user.id))

        return Response(_envelope(
            True, 'Registration successful.', data={'user': UserSerializer(user).data},
        ), status=status.HTTP_201_CREATED)


class LoginAPIView(GenericAPIView):
    serializer_class = LoginSerializer
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'login'

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']

        reset_login_failures(user)
        login(request, user)
        request.session.pop('is_admin_session', None)
        log_security_event(request, 'auth.login', actor=user, target_type='user', target_id=str(user.id))

        return Response(_envelope(True, 'Login successful.', data={'user': UserSerializer(user).data}))


class LogoutAPIView(GenericAPIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        log_security_event(request, 'auth.logout', actor=request.user, target_type='user', target_id=str(request.user.id))
        logout(request)
        return Response(_envelope(True, 'Logged out successfully.'))


class UserProfileAPIView(RetrieveUpdateAPIView):
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        return Response(_envelope(True, 'Profile retrieved.', data=self.get_serializer(instance).data))

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(_envelope(True, 'Profile updated successfully.', data=serializer.data))


class ChangePasswordAPIView(GenericAPIView):
    serializer_class = ChangePasswordSerializer
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)

        user = request.user
        user.set_password(serializer.validated_data['new_password'])
        user.save()

        # Credential rotation invalidates every prior session (including the
        # current one), then re-establishes a fresh session for the user.
        revoke_all_sessions_for_user(user)
        logout(request)
        login(request, user)
        mark_credentials_changed(user)
        log_security_event(request, 'auth.password_changed', actor=user, target_type='user', target_id=str(user.id))

        return Response(_envelope(True, 'Password changed successfully.'))


class PasswordResetRequestAPIView(GenericAPIView):
    serializer_class = PasswordResetRequestSerializer
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'password_reset'

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']

        # Always answer generically to avoid revealing whether an account exists.
        try:
            user = User.objects.get(email__iexact=email, is_active=True)
        except User.DoesNotExist:
            return Response(_envelope(True, 'If the account exists, a reset link has been emailed.'))

        token = default_token_generator.make_token(user)
        exp = timezone.now() + timezone.timedelta(seconds=settings.PASSWORD_RESET_TIMEOUT)
        PasswordResetToken.objects.create(
            user=user,
            token_hash=PasswordResetToken.make_hash(token),
            expires_at=exp,
        )

        uid = urlsafe_base64_encode(str(user.pk).encode())
        reset_url = f'{settings.FRONTEND_URL}/accounts/reset-password?uid={uid}&token={token}'
        try:
            send_mail(
                subject='Your PhoneFix password reset link',
                message=(
                    f'Hi {user.first_name or user.email},\n\n'
                    f'We received a request to reset your password. '
                    f'This link expires in {settings.PASSWORD_RESET_TIMEOUT // 3600} hours and can only be used once:\n\n'
                    f'{reset_url}\n\n'
                    'If you did not request this, you can ignore this email.\n'
                    '— PhoneFix team'
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=True,
            )
        except Exception:  # noqa: BLE001 - delivery failures never leak account existence on success path
            log_security_event(request, 'auth.password_reset_email_failed', actor=user, target_type='user', target_id=str(user.id))

        log_security_event(request, 'auth.password_reset_requested', actor=user, target_type='user', target_id=str(user.id))
        return Response(_envelope(True, 'If the account exists, a reset link has been emailed.'))


class PasswordResetConfirmAPIView(GenericAPIView):
    serializer_class = PasswordResetConfirmSerializer
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'password_reset'

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data['user']
        reset = serializer.validated_data['reset']

        user.set_password(serializer.validated_data['new_password'])
        user.save()
        reset.used_at = timezone.now()
        reset.save(update_fields=['used_at'])

        # Any authenticated sessions for this account are now stale.
        revoke_all_sessions_for_user(user)
        mark_credentials_changed(user)
        log_security_event(request, 'auth.password_reset', actor=user, target_type='user', target_id=str(user.id))

        return Response(_envelope(True, 'Password has been reset. Please sign in.'))


class VerifyEmailAPIView(GenericAPIView):
    authentication_classes = []

    class _Serializer(PasswordResetConfirmSerializer):
        """Reuses uid/token validation but requires no password fields."""

    serializer_class = _Serializer
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        uid = kwargs.get('uid')
        token = kwargs.get('token')
        try:
            from django.utils.http import urlsafe_base64_decode
            from django.contrib.auth import get_user_model
            user_id = urlsafe_base64_decode(uid).decode()
            user = get_user_model().objects.get(pk=user_id)
            valid = default_token_generator.check_token(user, token)
        except Exception:  # noqa: BLE001
            valid = False

        if not valid:
            return Response(_envelope(False, 'Verification link is invalid or has expired.'), status=status.HTTP_400_BAD_REQUEST)

        user.is_verified = True
        user.save(update_fields=['is_verified'])
        log_security_event(request, 'auth.email_verified', actor=user, target_type='user', target_id=str(user.id))
        return Response(_envelope(True, 'Email verified successfully.'))


# ---------------------------------------------------------------------------
# Admin area authentication (distinct login endpoint + admin data isolation)
# ---------------------------------------------------------------------------
class AdminLoginAPIView(GenericAPIView):
    serializer_class = LoginSerializer
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'login'

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']

        if not is_admin_account(user):
            return Response(_envelope(False, 'This account is not authorized for the admin area.'), status=status.HTTP_403_FORBIDDEN)

        reset_login_failures(user)
        login(request, user)
        request.session['is_admin_session'] = True
        log_security_event(request, 'auth.admin_login', actor=user, target_type='user', target_id=str(user.id))

        return Response(_envelope(
            True, 'Admin login successful.',
            data={'user': UserSerializer(user).data, 'role': user.role, 'is_admin': True},
        ))


class AdminLogoutAPIView(GenericAPIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        log_security_event(request, 'auth.admin_logout', actor=request.user, target_type='user', target_id=str(request.user.id))
        logout(request)
        return Response(_envelope(True, 'Logged out of the admin area.'))


class AdminProfileAPIView(GenericAPIView):
    permission_classes = [IsAdminUser]

    def get(self, request, *args, **kwargs):
        return Response(_envelope(
            True, 'Admin profile.',
            data={'user': UserSerializer(request.user).data, 'role': request.user.role, 'is_admin': True},
        ))


# ---------------------------------------------------------------------------
# Customer address management (ownership-scoped; no cross-user access)
# ---------------------------------------------------------------------------
class AddressCreateAPIView(GenericAPIView):
    serializer_class = AddressCreateSerializer
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        is_default = serializer.validated_data.get('is_default', False)
        if is_default:
            Address.objects.filter(user=request.user, is_default=True).update(is_default=False)

        address = serializer.save(user=request.user)
        return Response(_envelope(
            True, 'Address created successfully.', data=AddressSerializer(address).data,
        ), status=status.HTTP_201_CREATED)


class AddressListAPIView(ListAPIView):
    serializer_class = AddressSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Address.objects.filter(user=self.request.user)

    def list(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.get_queryset(), many=True)
        return Response(_envelope(True, 'Addresses retrieved.', data=serializer.data))


def _get_owned_address(user, address_id):
    return Address.objects.filter(user=user, id=address_id).first()


class AddressUpdateAPIView(GenericAPIView):
    serializer_class = AddressCreateSerializer
    permission_classes = [IsAuthenticated]

    def put(self, request, *args, **kwargs):
        address = _get_owned_address(request.user, kwargs.get('address_id'))
        if address is None:
            return Response(_envelope(False, 'Address not found.'), status=status.HTTP_404_NOT_FOUND)

        serializer = self.get_serializer(address, data=request.data)
        serializer.is_valid(raise_exception=True)

        is_default = serializer.validated_data.get('is_default', False)
        if is_default:
            Address.objects.filter(user=request.user, is_default=True).exclude(id=address.id).update(is_default=False)

        address = serializer.save()
        return Response(_envelope(True, 'Address updated successfully.', data=AddressSerializer(address).data))


class AddressDeleteAPIView(GenericAPIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, *args, **kwargs):
        address = _get_owned_address(request.user, kwargs.get('address_id'))
        if address is None:
            return Response(_envelope(False, 'Address not found.'), status=status.HTTP_404_NOT_FOUND)

        was_default = address.is_default
        address.delete()

        if was_default:
            first = Address.objects.filter(user=request.user, is_default=True).first()
            if first:
                first.is_default = True
                first.save()

        return Response(_envelope(True, 'Address deleted successfully.'))


class AddressSetDefaultAPIView(GenericAPIView):
    permission_classes = [IsAuthenticated]

    def put(self, request, *args, **kwargs):
        address = _get_owned_address(request.user, kwargs.get('address_id'))
        if address is None:
            return Response(_envelope(False, 'Address not found.'), status=status.HTTP_404_NOT_FOUND)

        Address.objects.filter(user=request.user, is_default=True).update(is_default=False)
        address.is_default = True
        address.save()

        return Response(_envelope(True, 'Default address updated successfully.', data=AddressSerializer(address).data))