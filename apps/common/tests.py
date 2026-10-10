"""Security-focused tests: session auth, lockout, authorization, password flows."""

from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode
from django.utils import timezone
from rest_framework.test import APIClient

from django.test import TestCase

from apps.common.models import PasswordResetToken

User = get_user_model()

REGISTER = '/api/v1/auth/register/'
LOGIN = '/api/v1/auth/login/'
LOGOUT = '/api/v1/auth/logout/'
PROFILE = '/api/v1/auth/profile/'
CHANGE_PASSWORD = '/api/v1/auth/change-password/'
RESET_REQUEST = '/api/v1/auth/password-reset/'
RESET_CONFIRM = '/api/v1/auth/password-reset/confirm/'
CSRF = '/api/v1/auth/csrf/'
ADMIN_LOGIN = '/api/v1/admin/auth/login/'
ADMIN_PROFILE = '/api/v1/admin/auth/profile/'
ADMIN_LOGOUT = '/api/v1/admin/auth/logout/'


class AuthBase(TestCase):
    def setUp(self):
        self.client = APIClient(raise_request_exception=False)

    def register(self, **overrides):
        payload = {
            'email': 'customer@example.com',
            'password': 'Str0ng!Pass',
            'confirm_password': 'Str0ng!Pass',
            'full_name': 'Test Customer',
            'mobile': '+919876543210',
        }
        payload.update(overrides)
        return self.client.post(REGISTER, payload, format='json')

    def user(self, email='user@example.com', password='Str0ng!Pass', **kwargs):
        u = User.objects.create_user(email=email, password=password)
        for k, v in kwargs.items():
            setattr(u, k, v)
        u.save(update_fields=list(kwargs.keys()))
        return u


class SessionAuthTest(AuthBase):
    def test_register_creates_customer_session_and_no_tokens(self):
        resp = self.register()
        self.assertEqual(resp.status_code, 201)
        data = resp.json()['data']
        self.assertNotIn('tokens', data or {})
        user = User.objects.get(email='customer@example.com')
        self.assertEqual(user.role, 'customer')
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_admin)

        profile = self.client.get(PROFILE)
        self.assertEqual(profile.status_code, 200)
        self.assertEqual(profile.json()['data']['role'], 'customer')

    def test_register_ignores_client_supplied_admin_fields(self):
        resp = self.register(
            role='admin',
            is_staff=True,
            is_superuser=True,
        )
        self.assertEqual(resp.status_code, 201)
        user = User.objects.get(email='customer@example.com')
        self.assertEqual(user.role, 'customer')
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertFalse(user.is_admin)

    def test_register_rejects_mismatched_passwords(self):
        resp = self.register(confirm_password='Different1!')
        self.assertEqual(resp.status_code, 400)

    def test_login_uses_session_and_returns_no_tokens(self):
        self.user('a@example.com')
        resp = self.client.post(LOGIN, {'email': 'a@example.com', 'password': 'Str0ng!Pass'}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn('tokens', resp.json().get('data', {}))
        self.assertEqual(self.client.get(PROFILE).status_code, 200)

    def test_logout_clears_server_session(self):
        self.user('a@example.com')
        self.client.post(LOGIN, {'email': 'a@example.com', 'password': 'Str0ng!Pass'}, format='json')
        self.assertEqual(self.client.get(PROFILE).status_code, 200)
        resp = self.client.post(LOGOUT)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(self.client.get(PROFILE).status_code, (401, 403))

    def test_login_error_is_generic(self):
        resp = self.client.post(LOGIN, {'email': 'nobody@example.com', 'password': 'wrong'}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('Invalid email or password.', resp.json()['non_field_errors'])

    def test_wrong_password_does_not_reveal_account(self):
        self.user('a@example.com')
        wrong = self.client.post(LOGIN, {'email': 'a@example.com', 'password': 'wrong'}, format='json')
        self.assertEqual(wrong.status_code, 400)
        self.assertIn('Invalid email or password.', wrong.json()['non_field_errors'])


class LockoutTest(AuthBase):
    def test_account_locks_after_max_attempts_even_with_correct_password(self):
        user = self.user('a@example.com')
        for i in range(5):
            resp = self.client.post(LOGIN, {'email': 'a@example.com', 'password': f'wrong{i}'}, format='json')
            self.assertEqual(resp.status_code, 400)
        user.refresh_from_db()
        self.assertTrue(user.is_locked)

        resp = self.client.post(LOGIN, {'email': 'a@example.com', 'password': 'Str0ng!Pass'}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('locked', resp.json()['non_field_errors'][0].lower())

    def test_successful_login_resets_failure_counter(self):
        user = self.user('a@example.com')
        self.client.post(LOGIN, {'email': 'a@example.com', 'password': 'wrong0'}, format='json')
        user.refresh_from_db()
        self.assertEqual(user.failed_login_attempts, 1)

        self.client.post(LOGIN, {'email': 'a@example.com', 'password': 'Str0ng!Pass'}, format='json')
        user.refresh_from_db()
        self.assertEqual(user.failed_login_attempts, 0)
        self.assertIsNone(user.locked_until)


class AuthorizationTest(AuthBase):
    def make_admin(self, email='admin@example.com', password='Str0ng!Pass'):
        u = self.user(email=email, password=password, role='admin', is_staff=True)
        return u

    def test_anonymous_denied_on_protected_endpoint_by_default(self):
        resp = self.client.get(PROFILE)
        self.assertIn(resp.status_code, (401, 403))

    def test_customer_cannot_enter_admin_area(self):
        self.user('c@example.com')
        self.client.post(LOGIN, {'email': 'c@example.com', 'password': 'Str0ng!Pass'}, format='json')
        resp = self.client.post(ADMIN_LOGIN, {'email': 'c@example.com', 'password': 'Str0ng!Pass'}, format='json')
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(self.client.get(ADMIN_PROFILE).status_code, 403)

    def test_admin_login_grants_admin_area_access(self):
        self.make_admin()
        resp = self.client.post(ADMIN_LOGIN, {'email': 'admin@example.com', 'password': 'Str0ng!Pass'}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['data']['is_admin'], True)
        self.assertEqual(self.client.get(ADMIN_PROFILE).status_code, 200)

    def test_admin_profile_returns_role(self):
        self.make_admin()
        self.client.post(ADMIN_LOGIN, {'email': 'admin@example.com', 'password': 'Str0ng!Pass'}, format='json')
        resp = self.client.get(ADMIN_PROFILE)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['data']['role'], 'admin')

    def test_admin_can_access_client_profile(self):
        self.make_admin()
        self.client.post(LOGIN, {'email': 'admin@example.com', 'password': 'Str0ng!Pass'}, format='json')
        resp = self.client.get(PROFILE)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['data']['is_admin'], True)

    def test_profile_update_cannot_escalate_role(self):
        self.user('c@example.com')
        self.client.post(LOGIN, {'email': 'c@example.com', 'password': 'Str0ng!Pass'}, format='json')
        # role is surfaced read-only and any client attempt to set it is rejected.
        resp = self.client.put(PROFILE, {'role': 'admin', 'is_staff': True}, format='json')
        self.assertIn(resp.status_code, (400, 200))
        u = User.objects.get(email='c@example.com')
        self.assertEqual(u.role, 'customer')
        self.assertFalse(u.is_staff)


class ChangePasswordTest(AuthBase):
    def test_change_password_requires_old_and_updates_credentials(self):
        self.user('c@example.com')
        self.client.post(LOGIN, {'email': 'c@example.com', 'password': 'Str0ng!Pass'}, format='json')

        bad = self.client.post(CHANGE_PASSWORD, {
            'old_password': 'wrong-old',
            'new_password': 'NewPass!123',
            'confirm_password': 'NewPass!123',
        }, format='json')
        self.assertEqual(bad.status_code, 400)

        ok = self.client.post(CHANGE_PASSWORD, {
            'old_password': 'Str0ng!Pass',
            'new_password': 'NewPass!123',
            'confirm_password': 'NewPass!123',
        }, format='json')
        self.assertEqual(ok.status_code, 200)

        # Fresh session re-established for the same client.
        self.assertEqual(self.client.get(PROFILE).status_code, 200)

        # Old password no longer works.
        self.client.post(LOGOUT)
        old = self.client.post(LOGIN, {'email': 'c@example.com', 'password': 'Str0ng!Pass'}, format='json')
        self.assertEqual(old.status_code, 400)
        new = self.client.post(LOGIN, {'email': 'c@example.com', 'password': 'NewPass!123'}, format='json')
        self.assertEqual(new.status_code, 200)

    def test_change_password_revokes_other_sessions(self):
        self.user('c@example.com')
        self.client.post(LOGIN, {'email': 'c@example.com', 'password': 'Str0ng!Pass'}, format='json')
        other = APIClient(raise_request_exception=False)
        other.post(LOGIN, {'email': 'c@example.com', 'password': 'Str0ng!Pass'}, format='json')
        self.assertEqual(other.get(PROFILE).status_code, 200)

        self.client.post(CHANGE_PASSWORD, {
            'old_password': 'Str0ng!Pass',
            'new_password': 'NewPass!123',
            'confirm_password': 'NewPass!123',
        }, format='json')

        self.assertIn(other.get(PROFILE).status_code, (401, 403))


class PasswordResetTest(AuthBase):
    def test_request_never_discloses_account_existence(self):
        self.user('known@example.com')
        r1 = self.client.post(RESET_REQUEST, {'email': 'nobody@example.com'}, format='json')
        r2 = self.client.post(RESET_REQUEST, {'email': 'known@example.com'}, format='json')
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(r1.json()['message'], r2.json()['message'])

    def test_reset_token_is_single_use_and_changes_password(self):
        user = self.user('known@example.com')
        self.client.post(RESET_REQUEST, {'email': 'known@example.com'}, format='json')

        token = default_token_generator.make_token(user)
        uid = urlsafe_base64_encode(str(user.pk).encode())

        self.assertTrue(PasswordResetToken.objects.filter(user=user).exists())
        stored = PasswordResetToken.objects.get(user=user)
        self.assertNotEqual(stored.token_hash, token)

        first = self.client.post(RESET_CONFIRM, {
            'uid': uid,
            'token': token,
            'new_password': 'ResetPass!1',
            'confirm_password': 'ResetPass!1',
        }, format='json')
        self.assertEqual(first.status_code, 200)

        user.refresh_from_db()
        self.assertTrue(user.check_password('ResetPass!1'))
        stored.refresh_from_db()
        self.assertIsNotNone(stored.used_at)

        second = self.client.post(RESET_CONFIRM, {
            'uid': uid,
            'token': token,
            'new_password': 'Another!2',
            'confirm_password': 'Another!2',
        }, format='json')
        self.assertEqual(second.status_code, 400)

    def test_reset_with_bogus_token_rejected(self):
        user = self.user('known@example.com')
        self.client.post(RESET_REQUEST, {'email': 'known@example.com'}, format='json')
        resp = self.client.post(RESET_CONFIRM, {
            'uid': urlsafe_base64_encode(str(user.pk).encode()),
            'token': 'bogus-token',
            'new_password': 'ResetPass!1',
            'confirm_password': 'ResetPass!1',
        }, format='json')
        self.assertEqual(resp.status_code, 400)


class CSRFTest(AuthBase):
    def test_csrf_endpoint_issues_cookie(self):
        resp = self.client.get(CSRF)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('csrftoken', resp.cookies)