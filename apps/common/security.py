"""Security helpers: audit logging, brute-force lockout, session revocation.

These must never log passwords, session keys or reset tokens.
"""

import logging

from django.conf import settings
from django.contrib.sessions.models import Session
from django.utils import timezone

from apps.common.models import AuditLog

logger = logging.getLogger(__name__)


def get_client_ip(request):
    if request is None:
        return None
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    if xff:
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def log_security_event(request, action, actor=None, target_type='', target_id='', metadata=None):
    """Persist a security-relevant event.

    ``metadata`` is stored as-is; callers must never pass passwords, session
    secrets, reset tokens or access tokens.
    """
    try:
        AuditLog.objects.create(
            actor=actor or (getattr(request, 'user', None) if hasattr(request, 'user') else None),
            action=action,
            target_type=target_type,
            target_id=target_id,
            ip_address=get_client_ip(request),
            user_agent=(request.META.get('HTTP_USER_AGENT', '') if request else '')[:255],
            metadata=metadata or {},
        )
    except Exception as exc:  # noqa: BLE001 - audit failures must not break requests
        logger.error('Failed to persist audit event "%s": %s', action, exc)


def account_is_locked(user):
    return bool(user.is_locked)


def record_login_failure(user):
    """Increment the attempt counter and lock progressively after thresholds."""
    user.failed_login_attempts += 1
    if user.failed_login_attempts >= settings.MAX_LOGIN_ATTEMPTS:
        user.locked_until = timezone.now() + timezone.timedelta(minutes=settings.ACCOUNT_LOCKOUT_MINUTES)
        user.failed_login_attempts = 0
    user.save(update_fields=['failed_login_attempts', 'locked_until'])


def reset_login_failures(user):
    if user.failed_login_attempts or user.locked_until:
        user.failed_login_attempts = 0
        user.locked_until = None
        user.save(update_fields=['failed_login_attempts', 'locked_until'])


def revoke_all_sessions_for_user(user):
    """Delete every server-side session belonging to the user."""
    for session in Session.objects.filter(expire_date__gt=timezone.now()):
        data = session.get_decoded()
        if str(data.get('_auth_user_id')) == str(user.id):
            session.delete()


def mark_credentials_changed(user):
    user.last_password_change = timezone.now()
    user.save(update_fields=['last_password_change'])