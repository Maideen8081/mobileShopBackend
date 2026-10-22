"""Admin dashboard statistics and customer management endpoints."""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.orders.models import Order
from apps.repairs.models import RepairTicket

User = get_user_model()


def make_order(user, total, status='order_placed'):
    return Order.objects.create(
        user=user, shipping_address={}, subtotal=total, tax=0, shipping_charge=0,
        grand_total=Decimal(total), order_status=status,
    )


class AdminPanelBase(TestCase):
    def setUp(self):
        self.client = APIClient(raise_request_exception=False)
        self.admin = User.objects.create_user(email='admin@example.com', password='Str0ng!Pass', role='admin', is_staff=True)
        self.customer = User.objects.create_user(
            email='asha@example.com', password='Str0ng!Pass', first_name='Asha', last_name='Rao', mobile_number='9876543210'
        )
        self.client.force_authenticate(self.admin)


class DashboardTest(AdminPanelBase):
    def test_requires_admin(self):
        self.client.force_authenticate(self.customer)
        self.assertEqual(self.client.get('/api/v1/admin/dashboard/').status_code, 403)

    def test_kpis_reflect_real_data_and_skip_cancelled_orders(self):
        make_order(self.customer, '1500')
        make_order(self.customer, '900', status='cancelled')
        RepairTicket.objects.create(
            customer_name='Asha', mobile_number='9876543210', device_brand='Apple', device_model='iPhone 12',
            issue_category='Screen', problem_description='Cracked', priority='urgent',
        )
        data = self.client.get('/api/v1/admin/dashboard/').data['data']
        kpis = data['kpis']
        self.assertEqual(kpis['todaySales'], 1500.0)
        self.assertEqual(kpis['ordersTotal'], 2)
        self.assertEqual(kpis['repairsOpen'], 1)
        self.assertEqual(kpis['repairsUrgent'], 1)
        self.assertEqual(kpis['customersTotal'], 1)  # the admin is not a customer
        self.assertEqual(len(data['salesTrend']), 14)
        self.assertEqual(len(data['revenueTrend']), 6)
        self.assertEqual(data['salesTrend'][-1]['revenue'], 1500.0)
        self.assertEqual(len(data['recentOrders']), 2)


class CustomerAdminTest(AdminPanelBase):
    def test_list_excludes_admins_and_aggregates_orders(self):
        make_order(self.customer, '1200')
        make_order(self.customer, '800', status='cancelled')
        body = self.client.get('/api/v1/admin/customers/').data['data']
        self.assertEqual(body['count'], 1)
        row = body['results'][0]
        self.assertEqual(row['email'], 'asha@example.com')
        self.assertEqual(row['ordersCount'], 2)
        self.assertEqual(row['totalSpent'], 1200.0)
        self.assertEqual(body['summary']['withOrders'], 1)

    def test_search_and_bad_paging(self):
        User.objects.create_user(email='bob@example.com', password='Str0ng!Pass', first_name='Bob')
        self.assertEqual(self.client.get('/api/v1/admin/customers/', {'search': 'asha'}).data['data']['count'], 1)
        self.assertEqual(self.client.get('/api/v1/admin/customers/', {'page': 'x'}).status_code, 400)

    def test_detail_and_deactivate(self):
        url = f'/api/v1/admin/customers/{self.customer.pk}/'
        self.assertEqual(self.client.get(url).data['data']['name'], 'Asha Rao')
        r = self.client.patch(url, {'is_active': False}, format='json')
        self.assertEqual(r.status_code, 200)
        self.customer.refresh_from_db()
        self.assertFalse(self.customer.is_active)
        self.assertEqual(self.client.patch(url, {'is_active': 'maybe'}, format='json').status_code, 400)

    def test_admin_accounts_are_not_reachable(self):
        self.assertEqual(self.client.get(f'/api/v1/admin/customers/{self.admin.pk}/').status_code, 404)
        self.assertEqual(self.client.patch(f'/api/v1/admin/customers/{self.admin.pk}/', {'is_active': False}, format='json').status_code, 404)
