"""Google sign-in: verify a Google ID token and resolve it to a local customer account.

The SPA uses Google Identity Services to obtain an ID token (a JWT signed by
Google). We verify its signature, issuer, audience (our client ID) and expiry
with google-auth, then map the stable ``sub`` claim to a user.
"""

import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from google.auth.exceptions import GoogleAuthError
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

from .models import Customer

logger = logging.getLogger(__name__)

User = get_user_model()

GOOGLE_ISSUERS = {'accounts.google.com', 'https://accounts.google.com'}


class GoogleSignInError(Exception):
    """A user-presentable reason why Google sign-in was refused."""

    def __init__(self, message, status_code=400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class _TimeoutRequest(google_requests.Request):
    """Fetching Google's signing certs must not hang a worker."""

    def __call__(self, *args, timeout=5, **kwargs):
        return super().__call__(*args, timeout=timeout, **kwargs)


def verify_google_credential(credential):
    """Return verified ID-token claims, or raise GoogleSignInError."""
    client_id = settings.GOOGLE_CLIENT_ID
    if not client_id:
        raise GoogleSignInError('Google sign-in is not available right now.', status_code=503)

    try:
        claims = id_token.verify_oauth2_token(credential, _TimeoutRequest(), client_id, clock_skew_in_seconds=10)
    except (ValueError, GoogleAuthError) as exc:
        logger.info('[google-auth] Rejected ID token: %s', exc)
        raise GoogleSignInError('Google sign-in failed. Please try again.')

    if claims.get('iss') not in GOOGLE_ISSUERS:
        raise GoogleSignInError('Google sign-in failed. Please try again.')
    if not claims.get('sub') or not claims.get('email'):
        raise GoogleSignInError('Your Google account did not share an email address.')
    if not claims.get('email_verified'):
        raise GoogleSignInError('Please verify your Google account email before signing in.')
    return claims


def resolve_google_user(claims):
    """Find, link or create the customer for verified Google claims.

    Returns ``(user, created)``. Linking by email is safe because Google has
    verified ownership of the address (``email_verified``).
    """
    sub = claims['sub']
    email = User.objects.normalize_email(claims['email']).lower()

    user = User.objects.filter(google_sub=sub).first()
    created = False

    if user is None:
        user = User.objects.filter(email__iexact=email).first()
        if user is not None:
            if user.is_admin:
                # Staff accounts sign in through the admin portal only.
                raise GoogleSignInError('This account cannot sign in with Google.', status_code=403)
            if user.google_sub and user.google_sub != sub:
                raise GoogleSignInError('This email is linked to a different Google account.', status_code=409)
            user.google_sub = sub
            user.is_verified = True
            user.save(update_fields=['google_sub', 'is_verified'])
        else:
            user, created = _create_google_user(sub, email, claims)

    if user.is_admin:
        raise GoogleSignInError('This account cannot sign in with Google.', status_code=403)
    if not user.is_active:
        raise GoogleSignInError('This account has been disabled. Please contact support.', status_code=403)

    if not created:
        _sync_google_profile(user, claims)
    return user, created


def _google_picture(claims):
    """The account photo URL, if Google sent a usable https one."""
    picture = (claims.get('picture') or '').strip()
    return picture if picture.startswith('https://') and len(picture) <= 1024 else ''


def _sync_google_profile(user, claims):
    """Keep the stored Google details current without overwriting what the customer set.

    The photo always follows the Google account (it changes there). Names are
    only filled in when blank, e.g. an email/password account linked to Google
    later, so an edited profile name is never replaced.
    """
    changed = []
    picture = _google_picture(claims)
    if picture and picture != user.avatar_url:
        user.avatar_url = picture
        changed.append('avatar_url')
    for field, claim in (('first_name', 'given_name'), ('last_name', 'family_name')):
        value = (claims.get(claim) or '').strip()[:150]
        if value and not getattr(user, field):
            setattr(user, field, value)
            changed.append(field)
    if changed:
        user.save(update_fields=changed)


def _create_google_user(sub, email, claims):
    try:
        with transaction.atomic():
            user = User(
                email=email,
                first_name=(claims.get('given_name') or '')[:150],
                last_name=(claims.get('family_name') or '')[:150],
                role=User.ROLE_CUSTOMER,
                is_verified=True,
                google_sub=sub,
                avatar_url=_google_picture(claims),
            )
            # No local password; the customer can set one later via password reset.
            user.set_unusable_password()
            user.save()
            Customer.objects.get_or_create(user=user)
            return user, True
    except IntegrityError:
        # Two simultaneous first sign-ins: the other request created the row.
        return User.objects.get(google_sub=sub), False
