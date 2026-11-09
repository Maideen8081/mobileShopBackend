"""Paid-order endpoint, coupon validation and coupon usage limits."""

from datetime import timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.utils import timezone

from apps.cart.models import Cart, CartItem
from apps.customers.models import Address
from apps.orders.models import Coupon, Order

from .tests import ORDER_CREATE, OrderSecurityBase

PAID_ORDER_CREATE = '/api/v1/order/create/'
COUPON_APPLY = '/api/v1/coupon/apply/'


def razorpay_client(amount_paise, signature_ok=True):
    client = MagicMock()
    client.order.fetch.return_value = {'id': 'order_rzp_1', 'amount': amount_paise}
    if signature_ok:
        client.utility.verify_payment_signature.return_value = True
    else:
        client.utility.verify_payment_signature.side_effect = Exception('bad signature')
    return client


class PaidOrderTests(OrderSecurityBase):
    def setUp(self):
        super().setUp()
        self.login_customer()
        self.address = Address.objects.create(
            user=self.customer, full_name='Cust', mobile_number='9876543210',
            house_number='12', city='Chennai', state='Tamil Nadu', pincode='600001',
        )
        cart = Cart.objects.create(user=self.customer)
        CartItem.objects.create(
            cart=cart, product=self.product, variant=self.variant,
            quantity=1, price=Decimal('10000.00'),
        )
        # 10000 + 18% GST, free shipping above the threshold.
        self.total_paise = 1180000

    def _payload(self, **overrides):
        payload = {
            'address_id': self.address.id,
            'razorpay_order_id': 'order_rzp_1',
            'razorpay_payment_id': 'pay_1',
            'razorpay_signature': 'sig',
        }
        payload.update(overrides)
        return payload

    def _post(self, client, **overrides):
        with patch('apps.orders.serializers.razorpay.Client', return_value=client), \
                patch('apps.orders.views.razorpay.Client', return_value=client), \
                patch('apps.orders.serializers.config', return_value='test'), \
                patch('apps.orders.views.config', return_value='test'):
            return self.client.post(PAID_ORDER_CREATE, self._payload(**overrides), format='json')

    def test_forged_signature_is_rejected(self):
        resp = self._post(razorpay_client(self.total_paise, signature_ok=False))
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(Order.objects.filter(razorpay_order_id='order_rzp_1').exists())
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.stock_quantity, 5)

    def test_verified_payment_creates_paid_order(self):
        resp = self._post(razorpay_client(self.total_paise))
        self.assertEqual(resp.status_code, 201, resp.content)
        order = Order.objects.get(razorpay_order_id='order_rzp_1')
        self.assertEqual(order.payment_status, 'paid')
        self.assertEqual(order.grand_total, Decimal('11800.00'))
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.stock_quantity, 4)
        self.assertFalse(Cart.objects.filter(user=self.customer).exists())

    def test_amount_mismatch_is_rejected(self):
        # Paid for a cheaper cart, then tried to check out a bigger one.
        resp = self._post(razorpay_client(100))
        self.assertEqual(resp.status_code, 400)
        self.assertIn('amount', resp.json()['message'].lower())
        self.assertFalse(Order.objects.filter(razorpay_order_id='order_rzp_1').exists())

    def test_payment_cannot_be_reused(self):
        Order.objects.create(
            user=self.customer, shipping_address={}, payment_method='razorpay',
            payment_status='paid', order_status='order_placed',
            subtotal=0, tax=0, shipping_charge=0, grand_total=0,
            razorpay_order_id='order_rzp_1',
        )
        resp = self._post(razorpay_client(self.total_paise))
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(Order.objects.filter(razorpay_order_id='order_rzp_1').count(), 1)

    def test_requires_login(self):
        self.client.logout()
        resp = self.client.post(PAID_ORDER_CREATE, self._payload(), format='json')
        self.assertIn(resp.status_code, (401, 403))


class CouponTests(OrderSecurityBase):
    def setUp(self):
        super().setUp()
        self.login_customer()
        self.coupon = Coupon.objects.create(
            code='SAVE10', discount_type='percentage', discount_value=Decimal('10'),
            minimum_amount=Decimal('1000'), expiry_date=timezone.now() + timedelta(days=5),
        )

    def apply(self, code, subtotal='10000.00'):
        return self.client.post(COUPON_APPLY, {'code': code, 'subtotal': subtotal}, format='json')

    def test_valid_coupon_returns_discount(self):
        resp = self.apply('save10')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()['data']
        self.assertEqual(data['coupon_code'], 'SAVE10')
        self.assertEqual(Decimal(data['discount_amount']), Decimal('1000.00'))

    def test_unknown_coupon_is_rejected(self):
        self.assertEqual(self.apply('PHONE10').status_code, 400)

    def test_expired_coupon_is_rejected(self):
        self.coupon.expiry_date = timezone.now() - timedelta(days=1)
        self.coupon.save()
        self.assertEqual(self.apply('SAVE10').status_code, 400)

    def test_minimum_amount_enforced(self):
        self.assertEqual(self.apply('SAVE10', subtotal='500.00').status_code, 400)

    def test_fixed_discount_never_exceeds_subtotal(self):
        Coupon.objects.create(
            code='BIG', discount_type='fixed', discount_value=Decimal('5000'),
            expiry_date=timezone.now() + timedelta(days=5),
        )
        resp = self.apply('BIG', subtotal='1200.00')
        self.assertEqual(Decimal(resp.json()['data']['discount_amount']), Decimal('1200.00'))

    def test_requires_login(self):
        self.client.logout()
        self.assertIn(self.apply('SAVE10').status_code, (401, 403))

    def _order(self):
        return self.client.post(ORDER_CREATE, {
            'items': [{'product_id': self.product.id, 'variant_id': self.variant.id,
                       'name': 'Nova X', 'price': '1', 'quantity': 1}],
            'total': '1', 'subtotal': '1', 'payment_method': 'cod', 'coupon_code': 'SAVE10',
        }, format='json')

    def test_order_counts_coupon_use_and_respects_max_uses(self):
        self.coupon.max_uses = 1
        self.coupon.save()

        first = self._order()
        self.assertEqual(first.status_code, 201, first.content)
        self.assertEqual(Decimal(first.json()['data']['discount']), Decimal('1000.00'))
        self.coupon.refresh_from_db()
        self.assertEqual(self.coupon.used_count, 1)

        second = self._order()
        self.assertEqual(second.status_code, 201)
        self.assertEqual(Decimal(second.json()['data']['discount']), Decimal('0.00'))
        self.coupon.refresh_from_db()
        self.assertEqual(self.coupon.used_count, 1)
