"""Cart API: add (with and without an explicit variant), update, remove, clear."""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.cart.models import CartItem
from apps.categories.models import Category
from apps.products.models import Product, ProductVariant

User = get_user_model()

CART = '/api/v1/cart/'
CART_ADD = '/api/v1/cart/add/'
CART_UPDATE = '/api/v1/cart/update-quantity/'
CART_CLEAR = '/api/v1/cart/clear/'


class CartAPITests(TestCase):
    def setUp(self):
        self.client = APIClient(raise_request_exception=False)
        self.user = User.objects.create_user(email='cart@example.com', password='Str0ng!Pass')
        self.client.force_authenticate(self.user)
        self.category = Category.objects.create(category_name='Phones', status='active')
        self.product = Product.objects.create(
            product_name='Nova X', brand='Nova', model_number='NX1', category=self.category,
        )
        self.expensive = ProductVariant.objects.create(
            product=self.product, variant_name='256GB', color='Black',
            ram_size='12', storage_size='256', price=Decimal('30000.00'),
            stock_quantity=5,
        )
        self.cheap = ProductVariant.objects.create(
            product=self.product, variant_name='128GB', color='Blue',
            ram_size='8', storage_size='128', price=Decimal('20000.00'),
            discount_price=Decimal('18000.00'), stock_quantity=3,
        )

    def add(self, **payload):
        return self.client.post(CART_ADD, payload, format='json')

    def test_add_with_explicit_variant(self):
        res = self.add(product_id=self.product.id, variation_id=self.expensive.id, quantity=2)
        self.assertEqual(res.status_code, 200, res.data)
        products = res.data['data']['products']
        self.assertEqual(len(products), 1)
        self.assertEqual(products[0]['variation_id'], self.expensive.id)
        self.assertEqual(products[0]['quantity'], 2)

    def test_add_without_variant_uses_cheapest_in_stock_variant(self):
        for payload in ({}, {'variation_id': 0}, {'variation_id': None}):
            CartItem.objects.all().delete()
            res = self.add(product_id=self.product.id, quantity=1, **payload)
            self.assertEqual(res.status_code, 200, (payload, res.data))
            self.assertEqual(res.data['data']['products'][0]['variation_id'], self.cheap.id)

    def test_add_without_variant_skips_out_of_stock_and_inactive(self):
        self.cheap.stock_quantity = 0
        self.cheap.save()
        res = self.add(product_id=self.product.id, variation_id=0)
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data['data']['products'][0]['variation_id'], self.expensive.id)

        self.expensive.is_active = False
        self.expensive.save()
        CartItem.objects.all().delete()
        res = self.add(product_id=self.product.id, variation_id=0)
        self.assertEqual(res.status_code, 400)
        self.assertIn('message', res.data)

    def test_add_existing_item_increments_and_respects_stock(self):
        self.add(product_id=self.product.id, variation_id=self.cheap.id, quantity=2)
        res = self.add(product_id=self.product.id, variation_id=self.cheap.id, quantity=1)
        self.assertEqual(res.data['data']['products'][0]['quantity'], 3)
        res = self.add(product_id=self.product.id, variation_id=self.cheap.id, quantity=1)
        self.assertEqual(res.status_code, 400)
        self.assertIn('Only 3 unit(s)', res.data['message'])

    def test_validation_errors_return_readable_message(self):
        res = self.add(product_id=999999, variation_id=0)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.data['message'], 'Product not found.')

        res = self.add(product_id=self.product.id, variation_id=self.cheap.id, quantity=10)
        self.assertEqual(res.status_code, 400)
        self.assertIn('Only 3 unit(s)', res.data['message'])

    def test_requires_authentication(self):
        self.client.force_authenticate(None)
        res = self.add(product_id=self.product.id, variation_id=self.cheap.id)
        self.assertIn(res.status_code, (401, 403))

    def test_cart_detail_reports_prices_and_discount(self):
        self.add(product_id=self.product.id, variation_id=self.cheap.id, quantity=1)
        data = self.client.get(CART).data['data']
        self.assertEqual(Decimal(data['subtotal']), Decimal('20000.00'))
        self.assertEqual(Decimal(data['discount']), Decimal('2000.00'))
        self.assertEqual(Decimal(data['products'][0]['discount_price']), Decimal('18000.00'))
        self.assertEqual(data['quantity'], 1)

    def test_update_remove_and_clear(self):
        res = self.add(product_id=self.product.id, variation_id=self.cheap.id, quantity=1)
        item_id = res.data['data']['products'][0]['cart_item_id']

        res = self.client.put(CART_UPDATE, {'cart_item_id': item_id, 'action': 'increase'}, format='json')
        self.assertEqual(res.data['data']['products'][0]['quantity'], 2)

        res = self.client.put(CART_UPDATE, {'cart_item_id': item_id, 'action': 'decrease'}, format='json')
        res = self.client.put(CART_UPDATE, {'cart_item_id': item_id, 'action': 'decrease'}, format='json')
        self.assertEqual(res.data['data']['products'], [])

        self.add(product_id=self.product.id, variation_id=self.cheap.id)
        res = self.client.delete(f'/api/v1/cart/remove/{CartItem.objects.get().id}/')
        self.assertEqual(res.data['data']['products'], [])

        self.add(product_id=self.product.id, variation_id=self.cheap.id)
        self.client.delete(CART_CLEAR)
        self.assertEqual(self.client.get(CART).data['data']['products'], [])
