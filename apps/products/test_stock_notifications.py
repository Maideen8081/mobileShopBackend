"""Back-in-stock notifications: subscribe endpoint and restock emails."""

from decimal import Decimal

from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.categories.models import Category

from .models import Product, ProductVariant, StockNotification


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class StockNotificationTest(TestCase):
    def setUp(self):
        cache.clear()  # throttle counters
        self.client = APIClient(raise_request_exception=False)
        cat = Category.objects.create(category_name='Chargers', status='active')
        self.product = Product.objects.create(
            product_name='Google 45W Charger', brand='Google', model_number='G45W', category=cat,
        )
        self.variant = ProductVariant.objects.create(
            product=self.product, variant_name='USB-C', color='White', ram_size='0', storage_size='0',
            price=Decimal('2999.00'), stock_quantity=0,
        )
        self.url = f'/api/v1/products/{self.product.id}/notify/'

    def subscribe(self, email='Shopper@Example.com', variant_id=None):
        return self.client.post(self.url, {'email': email, 'variant_id': variant_id or self.variant.id}, format='json')

    def restock(self, qty=5):
        self.variant.stock_quantity = qty
        with self.captureOnCommitCallbacks(execute=True):
            self.variant.save()

    def test_subscribe_creates_pending_request(self):
        resp = self.subscribe()
        self.assertEqual(resp.status_code, 201)
        sub = StockNotification.objects.get()
        self.assertEqual((sub.email, sub.variant_id, sub.notified_at), ('shopper@example.com', self.variant.id, None))

    def test_duplicate_subscription_is_idempotent(self):
        self.subscribe()
        resp = self.subscribe(email='shopper@example.com')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(StockNotification.objects.count(), 1)

    def test_rejects_bad_email_unknown_variant_and_in_stock_items(self):
        self.assertEqual(self.subscribe(email='nope').status_code, 400)
        self.assertEqual(self.subscribe(variant_id=999999).status_code, 400)
        self.restock()
        self.assertEqual(self.subscribe().status_code, 400)

    def test_unknown_or_unpublished_product_is_404(self):
        self.product.is_published = False
        self.product.save()
        self.assertEqual(self.subscribe().status_code, 404)

    def test_restock_emails_subscribers_once(self):
        self.subscribe()
        self.restock()
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['shopper@example.com'])
        self.assertIn('Google 45W Charger', mail.outbox[0].subject)
        self.assertIsNotNone(StockNotification.objects.get().notified_at)

        # Further stock changes don't re-send.
        self.restock(qty=8)
        self.assertEqual(len(mail.outbox), 1)

    def test_stock_change_while_still_out_of_stock_sends_nothing(self):
        self.subscribe()
        self.variant.low_stock_alert = 3
        with self.captureOnCommitCallbacks(execute=True):
            self.variant.save()
        self.assertEqual(len(mail.outbox), 0)
