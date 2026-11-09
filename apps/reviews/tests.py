"""Reviews: public listing, moderation visibility, ownership and validation."""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.categories.models import Category, SubCategory
from apps.products.models import Product, ProductVariant
from apps.reviews.models import Review

User = get_user_model()

BASE = '/api/v1/reviews/'


class ReviewTests(TestCase):
    def setUp(self):
        self.client = APIClient(raise_request_exception=False)
        self.alice = User.objects.create_user(email='alice@example.com', password='Str0ng!Pass')
        self.bob = User.objects.create_user(email='bob@example.com', password='Str0ng!Pass')
        self.admin = User.objects.create_user(
            email='admin@example.com', password='Str0ng!Pass', role='admin', is_staff=True,
        )
        category = Category.objects.create(category_name='Phones', status='active')
        sub = SubCategory.objects.create(parent_category=category, sub_category_name='Smart', status='active')
        self.product = Product.objects.create(
            product_name='Nova X', brand='Nova', model_number='NX1', category=category, sub_category=sub,
        )
        ProductVariant.objects.create(
            product=self.product, variant_name='128GB', color='Black', ram_size='8',
            storage_size='128', price=Decimal('10000.00'), stock_quantity=5, is_active=True,
        )
        self.published = Review.objects.create(user=self.alice, product=self.product, star=5, content='Great')
        self.hidden = Review.objects.create(
            user=self.bob, product=self.product, star=1, content='Spam', is_published=False,
        )

    # --- listing -----------------------------------------------------------

    def test_public_list_shows_only_published_with_summary(self):
        resp = self.client.get(BASE, {'product': self.product.id})
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual([r['id'] for r in body['data']], [self.published.id])
        self.assertEqual(body['total_reviews'], 1)
        self.assertEqual(body['average_star'], 5)

    def test_public_cannot_list_hidden_reviews(self):
        resp = self.client.get(BASE, {'is_published': 'false'})
        ids = [r['id'] for r in resp.json()['data']]
        self.assertNotIn(self.hidden.id, ids)

    def test_admin_can_list_hidden_reviews(self):
        self.client.force_login(self.admin)
        resp = self.client.get(BASE, {'is_published': 'false'})
        self.assertEqual([r['id'] for r in resp.json()['data']], [self.hidden.id])

    def test_filter_by_star(self):
        resp = self.client.get(BASE, {'star': 1})
        self.assertEqual(resp.json()['data'], [])

    def test_hidden_review_detail_is_not_public(self):
        self.assertEqual(self.client.get(f'{BASE}{self.hidden.id}/').status_code, 404)
        self.assertEqual(self.client.get(f'{BASE}{self.published.id}/').status_code, 200)

    # --- creating ----------------------------------------------------------

    def test_create_requires_login(self):
        resp = self.client.post(f'{BASE}create/', {'product': self.product.id, 'star': 4}, format='json')
        self.assertIn(resp.status_code, (401, 403))

    def test_create_review(self):
        carol = User.objects.create_user(email='carol@example.com', password='Str0ng!Pass')
        self.client.force_login(carol)
        resp = self.client.post(
            f'{BASE}create/', {'product': self.product.id, 'star': 4, 'content': 'Nice'}, format='json',
        )
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(resp.json()['data']['user'], carol.id)

    def test_duplicate_review_is_a_clear_400_not_a_crash(self):
        self.client.force_login(self.alice)
        resp = self.client.post(f'{BASE}create/', {'product': self.product.id, 'star': 3}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('already reviewed', str(resp.json()))

    def test_star_out_of_range_rejected(self):
        carol = User.objects.create_user(email='carol@example.com', password='Str0ng!Pass')
        self.client.force_login(carol)
        for star in (0, 6):
            resp = self.client.post(f'{BASE}create/', {'product': self.product.id, 'star': star}, format='json')
            self.assertEqual(resp.status_code, 400)

    # --- ownership ---------------------------------------------------------

    def test_owner_can_update(self):
        self.client.force_login(self.alice)
        resp = self.client.patch(f'{BASE}{self.published.id}/update/', {'content': 'Edited'}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.published.refresh_from_db()
        self.assertEqual(self.published.content, 'Edited')

    def test_owner_cannot_republish_hidden_review(self):
        self.client.force_login(self.bob)
        self.client.patch(f'{BASE}{self.hidden.id}/update/', {'is_published': True}, format='json')
        self.hidden.refresh_from_db()
        self.assertFalse(self.hidden.is_published)

    def test_other_user_cannot_update_or_delete(self):
        self.client.force_login(self.bob)
        self.assertEqual(
            self.client.patch(f'{BASE}{self.published.id}/update/', {'content': 'x'}, format='json').status_code, 404,
        )
        self.assertEqual(self.client.delete(f'{BASE}{self.published.id}/delete/').status_code, 404)
        self.assertTrue(Review.objects.filter(id=self.published.id).exists())

    def test_owner_can_delete(self):
        self.client.force_login(self.alice)
        self.assertEqual(self.client.delete(f'{BASE}{self.published.id}/delete/').status_code, 200)
        self.assertFalse(Review.objects.filter(id=self.published.id).exists())

    def test_image_upload_requires_an_image_and_ownership(self):
        self.client.force_login(self.alice)
        resp = self.client.post(f'{BASE}{self.published.id}/images/upload/', {}, format='multipart')
        self.assertEqual(resp.status_code, 400)
        self.client.force_login(self.bob)
        resp = self.client.post(f'{BASE}{self.published.id}/images/upload/', {}, format='multipart')
        self.assertEqual(resp.status_code, 404)
