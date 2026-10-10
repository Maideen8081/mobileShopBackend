"""Authorization helpers and reusable permission classes."""

from rest_framework.permissions import BasePermission, SAFE_METHODS


def is_admin_account(user):
    """Authorize an admin from server-side state only.

    Never derives admin rights from URLs, query strings, request bodies,
    headers or anything client-supplied.
    """
    return bool(
        user is not None
        and user.is_authenticated
        and user.is_active
        and user.is_admin
    )


class IsAdminUser(BasePermission):
    """Deny unless the authenticated principal is an authorized administrator."""

    message = 'Administrator privileges are required for this action.'

    def has_permission(self, request, view):
        return is_admin_account(request.user)


class IsAdminOrReadOnly(BasePermission):
    """SAFE_METHODS are public; anything else requires an administrator."""

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return is_admin_account(request.user)