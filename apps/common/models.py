from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from django.utils import timezone


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('Email is required.')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('role', 'admin')
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    ROLE_CUSTOMER = 'customer'
    ROLE_ADMIN = 'admin'

    first_name = models.CharField(max_length=150, blank=True, default='')
    last_name = models.CharField(max_length=150, blank=True, default='')
    email = models.EmailField(unique=True, max_length=254)
    mobile_number = models.CharField(max_length=15, blank=True, null=True, default=None)
    role = models.CharField(max_length=20, default=ROLE_CUSTOMER)
    profile_image = models.ImageField(upload_to='users/', blank=True, null=True)
    is_verified = models.BooleanField(default=False)
    # Stable Google account id ('sub' claim) once the user signs in with Google.
    google_sub = models.CharField(max_length=255, unique=True, blank=True, null=True, default=None)
    # Profile photo URL from the Google account ('picture' claim), refreshed on each Google sign-in.
    avatar_url = models.URLField(max_length=1024, blank=True, default='')
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    date_joined = models.DateTimeField(auto_now_add=True)
    otp = models.CharField(max_length=6, blank=True, null=True)
    otp_created_at = models.DateTimeField(blank=True, null=True)

    # Brute-force protection / credential rotation metadata.
    failed_login_attempts = models.PositiveIntegerField(default=0)
    locked_until = models.DateTimeField(blank=True, null=True)
    last_password_change = models.DateTimeField(blank=True, null=True)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    class Meta:
        db_table = 'users'
        swappable = 'AUTH_USER_MODEL'

    def __str__(self):
        return self.email

    def get_full_name(self):
        return f'{self.first_name} {self.last_name}'.strip()

    def get_short_name(self):
        return self.first_name or self.email

    @property
    def is_locked(self):
        return bool(self.locked_until and self.locked_until > timezone.now())

    @property
    def is_admin(self):
        """Whether this account is authorized for the admin area.

        Authorization is derived exclusively from server-side state.
        """
        return bool(
            self.is_active
            and (
                self.is_superuser
                or self.is_staff
                or self.role in ('admin', 'superadmin')
            )
        )


class AuditLog(models.Model):
    """Immutable record of security-relevant actions.

    Never stores passwords, session keys, reset tokens or other secrets.
    """

    actor = models.ForeignKey(
        'common.User',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='audit_logs',
    )
    action = models.CharField(max_length=64, db_index=True)
    target_type = models.CharField(max_length=64, blank=True, default='')
    target_id = models.CharField(max_length=64, blank=True, default='')
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, blank=True, default='')
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'audit_logs'
        ordering = ('-created_at',)

    def __str__(self):
        return f'{self.action} by {self.actor_id or "anonymous"}'


class PasswordResetToken(models.Model):
    """Single-use, time-limited password reset token.

    Only a SHA-256 digest of the token is persisted; the raw token is never
    stored in the database or logged anywhere.
    """

    user = models.ForeignKey('common.User', on_delete=models.CASCADE, related_name='password_reset_tokens')
    token_hash = models.CharField(max_length=64, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'password_reset_tokens'

    @staticmethod
    def make_hash(token):
        import hashlib
        return hashlib.sha256(token.encode('utf-8')).hexdigest()
