"""Customer data isolation: address ownership is strictly enforced."""

from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from django.test import TestCase

from .models import Address

User = get_user_model()

ADDRESS_CREATE = '/api/v1/address/create/'
ADDRESS_LIST = '/api/v1/address/list/'


class AddressIsolationTest(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(email='alice@example.com', password='Al1cePass!')
        self.bob = User.objects.create_user(email='bob@example.com', password='B0bPass!')
        self.alice_client = APIClient(raise_request_exception=False)
        self.bob_client = APIClient(raise_request_exception=False)
        self.alice_client.force_login(self.alice)
        self.bob_client.force_login(self.bob)

        resp = self.alice_client.post(ADDRESS_CREATE, {
            'full_name': 'Alice',
            'mobile_number': '1111111111',
            'house_number': 'A1',
            'street_address': 'Main St',
            'city': 'City',
            'state': 'State',
            'pincode': '411001',
        }, format='json')
        self.assertEqual(resp.status_code, 201)
        self.alice_address = Address.objects.get(user=self.alice)

    def test_each_user_only_lists_own_addresses(self):
        self.bob_client.post(ADDRESS_CREATE, {
            'full_name': 'Bob',
            'mobile_number': '2222222222',
            'house_number': 'B2',
            'street_address': 'Other St',
            'city': 'Town',
            'state': 'State',
            'pincode': '411001',
        }, format='json')
        resp = self.bob_client.get(ADDRESS_LIST)
        ids = [a['address_id'] for a in resp.json()['data']]
        self.assertIn(Address.objects.get(user=self.bob).id, ids)
        self.assertNotIn(self.alice_address.id, ids)

    def test_address_update_is_ownership_scoped(self):
        resp = self.bob_client.put(
            f'/api/v1/address/update/{self.alice_address.id}/',
            {'full_name': 'Mallory', 'city': 'Hacked', 'state': 'X', 'pincode': '000000',
             'house_number': 'H', 'street_address': 'S', 'mobile_number': '3333333333'},
            format='json',
        )
        self.assertEqual(resp.status_code, 404)
        self.alice_address.refresh_from_db()
        self.assertNotEqual(self.alice_address.full_name, 'Mallory')

    def test_address_delete_is_ownership_scoped(self):
        resp = self.bob_client.delete(f'/api/v1/address/delete/{self.alice_address.id}/')
        self.assertEqual(resp.status_code, 404)
        self.assertTrue(Address.objects.filter(id=self.alice_address.id).exists())

    def test_set_default_is_ownership_scoped(self):
        resp = self.bob_client.put(f'/api/v1/address/set-default/{self.alice_address.id}/')
        self.assertEqual(resp.status_code, 404)
        self.alice_address.refresh_from_db()
        self.assertFalse(self.alice_address.is_default)