"""Catalog permission tests: reads public, writes admin-only."""

from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from django.test import TestCase

User = get_user_model()

PRODUCT_LIST = '/api/v1/products/'
PRODUCT_CREATE = '/api/v1/products/create/'


class ProductPermissionTest(TestCase):
    def setUp(self):
        self.anon = APIClient(raise_request_exception=False)
        self.customer_client = APIClient(raise_request_exception=False)
        self.admin_client = APIClient(raise_request_exception=False)
        self.customer = User.objects.create_user(email='c@example.com', password='Str0ng!Pass')
        self.admin = User.objects.create_user(
            email='a@example.com', password='Str0ng!Pass', role='admin', is_staff=True,
        )
        self.customer_client.force_login(self.customer)
        self.admin_client.force_login(self.admin)

    def test_product_list_is_public(self):
        resp = self.anon.get(PRODUCT_LIST)
        self.assertEqual(resp.status_code, 200)

    def test_anonymous_cannot_create_product(self):
        resp = self.anon.post(PRODUCT_CREATE, {}, format='json')
        self.assertIn(resp.status_code, (401, 403))

    def test_customer_cannot_create_product(self):
        resp = self.customer_client.post(PRODUCT_CREATE, {}, format='json')
        self.assertEqual(resp.status_code, 403)

    def test_admin_passes_authorization_check(self):
        # Admin passes authorization; returns 400 (invalid payload), never 401/403.
        resp = self.admin_client.post(PRODUCT_CREATE, {}, format='json')
        self.assertNotIn(resp.status_code, (401, 403))


class CategoryWritePermissionTest(TestCase):
    def setUp(self):
        self.anon = APIClient(raise_request_exception=False)
        self.customer_client = APIClient(raise_request_exception=False)
        self.admin_client = APIClient(raise_request_exception=False)
        self.customer = User.objects.create_user(email='c@example.com', password='Str0ng!Pass')
        self.admin = User.objects.create_user(
            email='a@example.com', password='Str0ng!Pass', role='admin', is_staff=True,
        )
        self.customer_client.force_login(self.customer)
        self.admin_client.force_login(self.admin)

    def test_subcategory_create_requires_admin(self):
        url = '/api/v1/sub-categories/create/'
        self.assertIn(self.anon.post(url, {}, format='json').status_code, (401, 403))
        self.assertEqual(self.customer_client.post(url, {}, format='json').status_code, 403)
        self.assertNotIn(self.admin_client.post(url, {}, format='json').status_code, (401, 403))