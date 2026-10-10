"""Order security: admin-only management, server-side totals, stock integrity."""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient
from django.test import TestCase

from apps.categories.models import Category, SubCategory
from apps.orders.models import Coupon, Order
from apps.products.models import Product, ProductVariant

User = get_user_model()

ORDER_CREATE = '/api/v1/orders/create/'
ORDERS_LIST = '/api/v1/orders/list/'
UPDATE_STATUS = '/api/v1/orders/update-status/'
ADMIN_LOGIN = '/api/v1/admin/auth/login/'


class OrderSecurityBase(TestCase):
    def setUp(self):
        self.client = APIClient(raise_request_exception=False)
        self.customer = User.objects.create_user(email='cust@example.com', password='Str0ng!Pass')
        self.admin = User.objects.create_user(
            email='admin@example.com', password='Str0ng!Pass',
            role='admin', is_staff=True,
        )
        self.category = Category.objects.create(category_name='Phones', status='active')
        self.sub = SubCategory.objects.create(
            parent_category=self.category, sub_category_name='Smart', status='active'
        )
        self.product = Product.objects.create(
            product_name='Nova X', brand='Nova', model_number='NX1',
            category=self.category, sub_category=self.sub,
        )
        self.variant = ProductVariant.objects.create(
            product=self.product, variant_name='128GB', color='Black',
            ram_size='8', storage_size='128', price=Decimal('10000.00'),
            stock_quantity=5, is_active=True,
        )
        self.order = Order.objects.create(
            user=self.customer,
            shipping_address={'name': 'cust'},
            payment_method='cod',
            payment_status='pending',
            order_status='order_placed',
            subtotal=Decimal('20000.00'),
            tax=Decimal('3600.00'),
            shipping_charge=Decimal('0.00'),
            grand_total=Decimal('23600.00'),
        )

    def login_customer(self):
        self.client.force_login(self.customer)

    def login_admin(self):
        self.client.force_login(self.admin)


class OrderAdminOnlyTest(OrderSecurityBase):
    def test_anon_cannot_change_order_status(self):
        resp = self.client.put(f'{UPDATE_STATUS}{self.order.order_number}/', {'status': 'cancelled'}, format='json')
        self.assertIn(resp.status_code, (401, 403))

    def test_customer_cannot_change_order_status(self):
        self.login_customer()
        resp = self.client.put(f'{UPDATE_STATUS}{self.order.order_number}/', {'status': 'cancelled'}, format='json')
        self.assertEqual(resp.status_code, 403)

    def test_admin_can_change_order_status(self):
        self.login_admin()
        resp = self.client.put(f'{UPDATE_STATUS}{self.order.order_number}/', {'status': 'cancelled'}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.order.refresh_from_db()
        self.assertEqual(self.order.order_status, 'cancelled')
        self.assertEqual(self.order.payment_status, 'failed')

    def test_customer_cannot_list_all_orders(self):
        self.login_customer()
        self.assertEqual(self.client.get(ORDERS_LIST).status_code, 403)

    def test_admin_can_list_all_orders(self):
        self.login_admin()
        resp = self.client.get(ORDERS_LIST)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()['data']), 1)


class SimpleOrderIntegrityTest(OrderSecurityBase):
    def _payload(self, **overrides):
        payload = {
            'items': [{
                'product_id': self.product.id,
                'variant_id': self.variant.id,
                'name': 'Nova X',
                'price': '1.00',
                'quantity': 2,
            }],
            'total': '1.00',
            'subtotal': '1.00',
            'shipping': '1.00',
            'tax': '1.00',
            'discount': '1.00',
            'payment_method': 'cod',
        }
        payload.update(overrides)
        return payload

    def test_server_side_pricing_overrides_client_totals(self):
        self.login_customer()
        resp = self.client.post(ORDER_CREATE, self._payload(), format='json')
        self.assertEqual(resp.status_code, 201)

        order = Order.objects.filter(user=self.customer).order_by('-id').first()
        self.assertEqual(order.subtotal, Decimal('20000.00'))
        self.assertEqual(order.tax, Decimal('3600.00'))
        self.assertEqual(order.shipping_charge, Decimal('0.00'))
        self.assertEqual(order.discount, Decimal('0.00'))
        self.assertEqual(order.grand_total, Decimal('23600.00'))
        item = order.items.first()
        self.assertEqual(item.price, Decimal('10000.00'))
        self.assertEqual(item.total_price, Decimal('20000.00'))

    def test_client_discount_is_ignored_without_server_coupon(self):
        self.login_customer()
        resp = self.client.post(ORDER_CREATE, self._payload(discount='4999.99'), format='json')
        self.assertEqual(resp.status_code, 201)
        order = Order.objects.filter(user=self.customer).order_by('-id').first()
        self.assertEqual(order.discount, Decimal('0.00'))

    def test_stock_is_decremented(self):
        self.login_customer()
        self.client.post(ORDER_CREATE, self._payload(), format='json')
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.stock_quantity, 3)

    def test_insufficient_stock_is_rejected_and_nothing_persisted(self):
        self.login_customer()
        resp = self.client.post(
            ORDER_CREATE, self._payload(items=[{
                'product_id': self.product.id,
                'variant_id': self.variant.id,
                'name': 'Nova X', 'price': '1.00', 'quantity': 10,
            }]), format='json'
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(Order.objects.filter(user=self.customer).count(), 1)  # only setup order
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.stock_quantity, 5)

    def test_unpublished_product_cannot_be_ordered(self):
        self.product.is_published = False
        self.product.save(update_fields=['is_published'])
        self.login_customer()
        resp = self.client.post(ORDER_CREATE, self._payload(), format='json')
        self.assertEqual(resp.status_code, 400)

    def test_inactive_variant_cannot_be_ordered(self):
        self.variant.is_active = False
        self.variant.save(update_fields=['is_active'])
        self.login_customer()
        resp = self.client.post(ORDER_CREATE, self._payload(), format='json')
        self.assertEqual(resp.status_code, 400)

    def test_coupon_discount_applied_server_side(self):
        Coupon.objects.create(
            code='SAVE10', discount_type='percentage', discount_value=10,
            minimum_amount=0, expiry_date=timezone.now() + timezone.timedelta(days=1),
        )
        self.login_customer()
        resp = self.client.post(ORDER_CREATE, self._payload(coupon_code='SAVE10'), format='json')
        self.assertEqual(resp.status_code, 201)
        order = Order.objects.filter(user=self.customer).order_by('-id').first()
        self.assertEqual(order.discount, Decimal('2000.00'))
        self.assertEqual(order.grand_total, Decimal('21600.00'))

    def test_shipping_charged_below_threshold(self):
        self.variant.price = Decimal('100.00')
        self.variant.save(update_fields=['price'])
        self.login_customer()
        resp = self.client.post(ORDER_CREATE, self._payload(), format='json')
        # 2 * 100 = 200 subtotal (server-priced) is below the 500 threshold
        self.assertEqual(resp.status_code, 201)
        order = Order.objects.filter(user=self.customer).order_by('-id').first()
        self.assertEqual(order.shipping_charge, Decimal('49.00'))