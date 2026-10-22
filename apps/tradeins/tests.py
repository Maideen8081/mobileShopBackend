"""Trade-in submissions: validation, admin-only access and the status workflow."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.tradeins.models import TradeIn

User = get_user_model()

BASE = '/api/v1/trade-ins/'

VALID = {
    'customer_name': 'Priya Sharma',
    'customer_mobile': '98765 43210',
    'customer_email': 'Priya@Example.com',
    'device_brand': 'Apple',
    'device_model': 'iPhone 13',
    'device_storage': '128GB',
    'device_condition': 'Good - Minor Scratches',
    'estimated_value': '24500',
}


class TradeInBase(TestCase):
    def setUp(self):
        self.client = APIClient(raise_request_exception=False)
        self.customer = User.objects.create_user(email='cust@example.com', password='Str0ng!Pass')
        self.admin = User.objects.create_user(email='admin@example.com', password='Str0ng!Pass', role='admin', is_staff=True)

    def make_trade(self, **overrides):
        data = {k: v for k, v in VALID.items() if k != 'estimated_value'}
        data['customer_mobile'] = '9876543210'
        data.update(overrides)
        return TradeIn.objects.create(estimated_value=24500, **data)


class TradeInCreateTest(TradeInBase):
    def test_guest_can_submit_and_fields_are_normalised(self):
        response = self.client.post(BASE, VALID, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        trade = TradeIn.objects.get()
        self.assertEqual(trade.customer_mobile, '9876543210')
        self.assertEqual(trade.customer_email, 'priya@example.com')
        self.assertEqual(trade.status, 'pending')
        self.assertIsNone(trade.user)
        self.assertEqual(response.data['data']['trade_id'], f'TRD-{trade.pk:06d}')

    def test_signed_in_submission_is_linked_to_user(self):
        self.client.force_authenticate(self.customer)
        self.client.post(BASE, VALID, format='json')
        self.assertEqual(TradeIn.objects.get().user, self.customer)
        mine = self.client.get(f'{BASE}my-submissions/')
        self.assertEqual(len(mine.data['data']), 1)

    def test_rejects_invalid_fields(self):
        bad = {
            **VALID,
            'customer_name': 'J',
            'customer_mobile': '12345',
            'customer_email': 'not-an-email',
            'device_model': '',
            'device_storage': '3TB',
            'device_condition': 'Like new-ish',
            'estimated_value': '-5',
        }
        response = self.client.post(BASE, bad, format='json')
        self.assertEqual(response.status_code, 400)
        for field in ('customer_name', 'customer_mobile', 'customer_email', 'device_model',
                      'device_storage', 'device_condition', 'estimated_value'):
            self.assertIn(field, response.data, field)
        self.assertFalse(TradeIn.objects.exists())


class TradeInAdminAccessTest(TradeInBase):
    def test_list_and_actions_require_admin(self):
        trade = self.make_trade()
        self.assertIn(self.client.get(BASE).status_code, (401, 403))
        self.client.force_authenticate(self.customer)
        self.assertEqual(self.client.get(BASE).status_code, 403)
        self.assertEqual(self.client.put(f'{BASE}{trade.pk}/accept/', {'final_value': 1}).status_code, 403)
        self.assertEqual(self.client.delete(f'{BASE}{trade.pk}/').status_code, 403)

    def test_admin_lists_filters_and_counts(self):
        self.make_trade()
        self.make_trade(status='paid', final_value=20000, customer_name='Rahul Verma')
        self.client.force_authenticate(self.admin)
        self.assertEqual(len(self.client.get(BASE).data['data']), 2)
        self.assertEqual(len(self.client.get(BASE, {'status': 'paid'}).data['data']), 1)
        self.assertEqual(len(self.client.get(BASE, {'search': 'rahul'}).data['data']), 1)
        counts = self.client.get(f'{BASE}dashboard-counts/').data['data']
        self.assertEqual((counts['total'], counts['pending'], counts['paid']), (2, 1, 1))
        self.assertEqual(counts['totalPayout'], 20000.0)


class TradeInWorkflowTest(TradeInBase):
    def setUp(self):
        super().setUp()
        self.trade = self.make_trade()
        self.client.force_authenticate(self.admin)

    def url(self, action=''):
        return f'{BASE}{self.trade.pk}/{action + "/" if action else ""}'

    def test_full_happy_path(self):
        r = self.client.put(self.url('quote'), {'quoted_price': '22000', 'notes': 'Minor dent'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['data']['status'], 'reviewed')
        r = self.client.put(self.url('accept'), {'final_value': '21500'}, format='json')
        self.assertEqual(r.data['data']['status'], 'accepted')
        r = self.client.put(self.url('pay'), {'payment_method': 'upi'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.trade.refresh_from_db()
        self.assertEqual((self.trade.status, self.trade.payment_status), ('paid', 'completed'))
        self.assertIn('Minor dent', self.trade.admin_notes)

    def test_cannot_skip_to_paid_or_accept_without_price(self):
        r = self.client.put(self.url('pay'), {'payment_method': 'upi'}, format='json')
        self.assertEqual(r.status_code, 400)
        r = self.client.put(self.url('status'), {'status': 'accepted'}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('quoted price', r.data['message'])

    def test_amounts_must_be_positive(self):
        self.assertEqual(self.client.put(self.url('quote'), {'quoted_price': '0'}, format='json').status_code, 400)
        self.assertEqual(self.client.put(self.url('accept'), {'final_value': '-1'}, format='json').status_code, 400)

    def test_reject_needs_reason_and_is_terminal(self):
        self.assertEqual(self.client.put(self.url('reject'), {'rejection_reason': ' '}, format='json').status_code, 400)
        r = self.client.put(self.url('reject'), {'rejection_reason': 'IMEI is blacklisted'}, format='json')
        self.assertEqual(r.data['data']['status'], 'rejected')
        self.assertEqual(self.client.put(self.url('accept'), {'final_value': '100'}, format='json').status_code, 400)
        self.assertEqual(self.client.patch(self.url(), {'admin_notes': 'x'}, format='json').status_code, 400)

    def test_paid_trade_cannot_be_deleted(self):
        self.trade.status = 'paid'
        self.trade.final_value = 100
        self.trade.save()
        self.assertEqual(self.client.delete(self.url()).status_code, 400)
        self.assertTrue(TradeIn.objects.filter(pk=self.trade.pk).exists())

    def test_invalid_payment_method(self):
        self.client.put(self.url('accept'), {'final_value': '100'}, format='json')
        self.assertEqual(self.client.put(self.url('pay'), {'payment_method': 'bitcoin'}, format='json').status_code, 400)
