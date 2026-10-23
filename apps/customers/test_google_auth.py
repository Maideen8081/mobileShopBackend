"""Google sign-in: token verification outcomes, account creation and linking."""

from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.customers.models import Customer

User = get_user_model()

GOOGLE_URL = '/api/v1/auth/google/'
PROFILE_URL = '/api/v1/auth/profile/'
CLIENT_ID = 'test-client.apps.googleusercontent.com'
VERIFY = 'apps.customers.google_auth.id_token.verify_oauth2_token'


def claims(**overrides):
    base = {
        'iss': 'https://accounts.google.com',
        'aud': CLIENT_ID,
        'sub': '1234567890',
        'email': 'Joe@Gmail.com',
        'email_verified': True,
        'given_name': 'Joe',
        'family_name': 'Bloggs',
    }
    base.update(overrides)
    return base


@override_settings(GOOGLE_CLIENT_ID=CLIENT_ID)
class GoogleLoginTest(TestCase):
    def setUp(self):
        self.client = APIClient(raise_request_exception=False)

    def post(self, token='google-id-token'):
        return self.client.post(GOOGLE_URL, {'credential': token}, format='json')

    def test_first_sign_in_creates_customer_and_session(self):
        with mock.patch(VERIFY, return_value=claims()) as verify:
            response = self.post()
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data['data']['created'])
        # Audience must be pinned to our client ID.
        self.assertEqual(verify.call_args.args[2], CLIENT_ID)

        user = User.objects.get(email='joe@gmail.com')
        self.assertEqual(user.google_sub, '1234567890')
        self.assertEqual(user.first_name, 'Joe')
        self.assertTrue(user.is_verified)
        self.assertFalse(user.has_usable_password())
        self.assertEqual(user.role, User.ROLE_CUSTOMER)
        self.assertTrue(Customer.objects.filter(user=user).exists())

        # The session cookie authenticates follow-up requests.
        self.assertEqual(self.client.get(PROFILE_URL).status_code, 200)

    def test_returning_user_matched_by_sub_even_if_email_changed(self):
        with mock.patch(VERIFY, return_value=claims()):
            self.post()
        with mock.patch(VERIFY, return_value=claims(email='new@gmail.com')):
            response = self.post()
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data['data']['created'])
        self.assertEqual(User.objects.count(), 1)

    def test_links_existing_password_account_with_same_email(self):
        existing = User.objects.create_user(email='joe@gmail.com', password='Str0ng!Pass')
        with mock.patch(VERIFY, return_value=claims()):
            response = self.post()
        self.assertEqual(response.status_code, 200)
        existing.refresh_from_db()
        self.assertEqual(existing.google_sub, '1234567890')
        self.assertTrue(existing.check_password('Str0ng!Pass'))
        self.assertEqual(User.objects.count(), 1)

    def test_invalid_token_rejected(self):
        with mock.patch(VERIFY, side_effect=ValueError('Token expired')):
            response = self.post()
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.data['success'])
        self.assertEqual(User.objects.count(), 0)

    def test_unverified_email_rejected(self):
        with mock.patch(VERIFY, return_value=claims(email_verified=False)):
            response = self.post()
        self.assertEqual(response.status_code, 400)
        self.assertEqual(User.objects.count(), 0)

    def test_wrong_issuer_rejected(self):
        with mock.patch(VERIFY, return_value=claims(iss='https://evil.example.com')):
            response = self.post()
        self.assertEqual(response.status_code, 400)

    def test_admin_account_cannot_use_google(self):
        User.objects.create_user(email='joe@gmail.com', password='Str0ng!Pass', role='admin', is_staff=True)
        with mock.patch(VERIFY, return_value=claims()):
            response = self.post()
        self.assertEqual(response.status_code, 403)
        self.assertIsNone(User.objects.get(email='joe@gmail.com').google_sub)

    def test_disabled_account_refused(self):
        User.objects.create_user(email='joe@gmail.com', password='Str0ng!Pass', is_active=False)
        with mock.patch(VERIFY, return_value=claims()):
            response = self.post()
        self.assertEqual(response.status_code, 403)

    def test_email_bound_to_other_google_account_refused(self):
        User.objects.create_user(email='joe@gmail.com', password='Str0ng!Pass', google_sub='other-sub')
        with mock.patch(VERIFY, return_value=claims()):
            response = self.post()
        self.assertEqual(response.status_code, 409)

    def test_missing_credential(self):
        self.assertEqual(self.client.post(GOOGLE_URL, {}, format='json').status_code, 400)

    @override_settings(GOOGLE_CLIENT_ID='')
    def test_disabled_when_not_configured(self):
        self.assertEqual(self.post().status_code, 503)

    def test_real_verifier_rejects_garbage_token(self):
        # No mock: google-auth must refuse a malformed JWT before any network call.
        response = self.post('not-a-jwt')
        self.assertEqual(response.status_code, 400)
