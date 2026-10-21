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

# ── Product create / edit / delete ──

import io
import json
import shutil
import tempfile
from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.test import override_settings
from PIL import Image

from apps.cart.models import Cart, CartItem
from apps.categories.models import Category, SubCategory
from .models import Product, ProductVariant, VariantImage

MEDIA_ROOT = tempfile.mkdtemp()


def png(name='v.png'):
    buf = io.BytesIO()
    Image.new('RGB', (8, 8), 'blue').save(buf, 'PNG')
    return SimpleUploadedFile(name, buf.getvalue(), content_type='image/png')


def variant(**overrides):
    return {
        'variant_name': 'Black 128GB', 'color': 'Black', 'ram_size': '8GB', 'storage_size': '128GB',
        'battery_capacity': 5000, 'processor': 'Snapdragon 8', 'display_size': '6.5 inch',
        'camera_details': '50MP', 'price': 20000, 'discount_price': 18000, 'stock_quantity': 10,
        'low_stock_alert': 5, 'image_order': ['file:0'], **overrides,
    }


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class ProductCrudTest(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        self.admin = User.objects.create_user(email='a@example.com', password='Str0ng!Pass', role='admin', is_staff=True)
        self.client = APIClient(raise_request_exception=False)
        self.client.force_login(self.admin)
        self.cat = Category.objects.create(category_name='Phones')
        self.sub = SubCategory.objects.create(parent_category=self.cat, sub_category_name='Android')

    def payload(self, variants=None, files=1, **fields):
        data = {
            'product_name': 'Galaxy S', 'brand': 'Samsung', 'model_number': 'SM-S1', 'category': self.cat.id,
            'sub_category': self.sub.id, 'description': 'Nice phone', 'is_published': 'true',
            'features': json.dumps([{'feature_text': '120Hz display'}]),
            'care_instructions': json.dumps([{'instruction_text': 'Keep dry'}]),
            'variants': json.dumps(variants if variants is not None else [variant()]),
            **fields,
        }
        if files:
            data['variant_images'] = [png(f'v{i}.png') for i in range(files)]
        return data

    def create(self, **kw):
        return self.client.post('/api/v1/products/create/', self.payload(**kw), format='multipart')

    def update(self, pid, data):
        return self.client.put(f'/api/v1/products/{pid}/update/', data, format='multipart')

    # create

    def test_create_product_with_variants_and_images_in_order(self):
        resp = self.create(variants=[variant(), variant(color='Blue', image_order=['file:2', 'file:1'])], files=3)
        self.assertEqual(resp.status_code, 201, resp.data)
        product = Product.objects.get()
        v1, v2 = product.variants.all()  # stored in the order entered
        self.assertEqual((v1.color, v2.color), ('Black', 'Blue'))
        self.assertEqual(v1.images.count(), 1)
        self.assertEqual(v2.images.count(), 2)
        self.assertIn('v2', v2.images.get(is_main=True).image.name)  # first in image_order is main
        self.assertEqual(product.features.get().feature_text, '120Hz display')

    def test_create_requires_variant_and_image(self):
        self.assertEqual(self.create(variants=[]).status_code, 400)
        resp = self.create(variants=[variant(image_order=[])])
        self.assertEqual(resp.status_code, 400)
        self.assertIn('at least one image', str(resp.data))
        resp = self.create(files=0)
        self.assertEqual(resp.status_code, 400)
        self.assertIn('missing', str(resp.data))

    def test_variant_field_rules(self):
        cases = [
            (variant(price=0), 'greater than 0'),
            (variant(discount_price=25000), 'lower than the price'),
            (variant(stock_quantity=-1), 'negative'),
            (variant(battery_capacity=50), 'at least 500'),
            (variant(color='  '), 'color'),
            (variant(price='abc'), 'price'),
        ]
        for v, msg in cases:
            resp = self.create(variants=[v])
            self.assertEqual(resp.status_code, 400, v)
            self.assertIn(msg, str(resp.data), v)
        self.assertFalse(Product.objects.exists())

    def test_zero_discount_means_no_discount(self):
        resp = self.create(variants=[variant(discount_price=0)])
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertIsNone(ProductVariant.objects.get().discount_price)

    def test_duplicate_variant_combination_rejected(self):
        resp = self.create(variants=[variant(), variant(variant_name='Again', image_order=['file:1'])], files=2)
        self.assertEqual(resp.status_code, 400)
        self.assertIn('already has', str(resp.data))

    def test_unknown_variant_keys_are_ignored_not_500(self):
        resp = self.create(variants=[variant(images=['x'], product=999, created_at='now')])
        self.assertEqual(resp.status_code, 201, resp.data)

    def test_product_field_rules(self):
        self.assertEqual(self.create(product_name='X').status_code, 400)
        self.assertEqual(self.create(model_number='bad model!').status_code, 400)
        self.assertEqual(self.create(brand='').status_code, 400)
        self.assertEqual(self.create(description='x' * 5001).status_code, 400)

    def test_duplicate_brand_and_model_rejected(self):
        self.create()
        resp = self.create(brand='SAMSUNG', model_number='sm-s1')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('already exists', str(resp.data))

    def test_sub_category_must_match_category(self):
        other = Category.objects.create(category_name='Audio')
        other_sub = SubCategory.objects.create(parent_category=other, sub_category_name='Earbuds')
        resp = self.create(sub_category=other_sub.id)
        self.assertEqual(resp.status_code, 400)
        self.assertIn('does not belong', str(resp.data))
        # A category with sub categories requires one
        resp = self.create(sub_category='')
        self.assertEqual(resp.status_code, 400)
        # A category without sub categories doesn't
        resp = self.create(category=other.id, sub_category='', model_number='NO-SUB')
        self.assertEqual(resp.status_code, 400)  # Audio has Earbuds
        bare = Category.objects.create(category_name='Cables')
        resp = self.create(category=bare.id, sub_category='', model_number='NO-SUB')
        self.assertEqual(resp.status_code, 201, resp.data)

    def test_inactive_category_rejected(self):
        self.cat.status = 'inactive'
        self.cat.save()
        self.assertEqual(self.create().status_code, 400)

    def test_bad_image_rejected(self):
        data = self.payload(files=0)
        data['variant_images'] = [SimpleUploadedFile('x.gif', b'GIF89a', content_type='image/gif')]
        resp = self.client.post('/api/v1/products/create/', data, format='multipart')
        self.assertEqual(resp.status_code, 400)

    # edit

    def created(self, **kw):
        resp = self.create(**kw)
        self.assertEqual(resp.status_code, 201, resp.data)
        return resp.data['data']

    def test_edit_keeps_existing_variants_and_images(self):
        """Regression: editing used to recreate every variant and drop its images."""
        p = self.created()
        v = p['variants'][0]
        img_id = v['images'][0]['id']
        edited = variant(id=v['id'], price=21000, discount_price=None, image_order=[f'id:{img_id}'])
        resp = self.update(p['id'], {'product_name': 'Galaxy S Plus', 'variants': json.dumps([edited])})
        self.assertEqual(resp.status_code, 200, resp.data)
        variant_obj = ProductVariant.objects.get()
        self.assertEqual(variant_obj.id, v['id'])
        self.assertEqual(variant_obj.price, Decimal('21000'))
        self.assertEqual(list(variant_obj.images.values_list('id', flat=True)), [img_id])
        self.assertEqual(Product.objects.get().product_name, 'Galaxy S Plus')

    def test_edit_variant_without_image_order_keeps_images(self):
        p = self.created()
        v = p['variants'][0]
        edited = variant(id=v['id'], stock_quantity=3)
        del edited['image_order']
        resp = self.update(p['id'], {'variants': json.dumps([edited])})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(VariantImage.objects.count(), 1)

    def test_edit_cart_items_survive(self):
        p = self.created()
        v = ProductVariant.objects.get()
        cart = Cart.objects.create(user=self.admin)
        CartItem.objects.create(cart=cart, product_id=p['id'], variant=v, quantity=1, price=v.price)
        edited = variant(id=v.id, stock_quantity=7)
        del edited['image_order']
        self.update(p['id'], {'variants': json.dumps([edited])})
        self.assertEqual(CartItem.objects.count(), 1)

    def test_edit_reorders_adds_and_removes_images(self):
        p = self.created(variants=[variant(image_order=['file:0', 'file:1'])], files=2)
        v = p['variants'][0]
        first, second = [img['id'] for img in v['images']]
        edited = variant(id=v['id'], image_order=[f'id:{second}', 'file:0'])  # drop first, new one appended
        resp = self.update(p['id'], {'variants': json.dumps([edited]), 'variant_images': [png('new.png')]})
        self.assertEqual(resp.status_code, 200, resp.data)
        imgs = list(VariantImage.objects.order_by('-is_main', 'id'))
        self.assertEqual(len(imgs), 2)
        self.assertEqual(imgs[0].id, second)
        self.assertTrue(imgs[0].is_main)
        self.assertFalse(VariantImage.objects.filter(pk=first).exists())

    def test_edit_cannot_remove_all_images_or_steal_images(self):
        p = self.created()
        v = p['variants'][0]
        resp = self.update(p['id'], {'variants': json.dumps([variant(id=v['id'], image_order=[])])})
        self.assertEqual(resp.status_code, 400)
        other = self.created(model_number='OTHER')
        foreign = other['variants'][0]['images'][0]['id']
        resp = self.update(p['id'], {'variants': json.dumps([variant(id=v['id'], image_order=[f'id:{foreign}'])])})
        self.assertEqual(resp.status_code, 400)
        self.assertIn('does not belong', str(resp.data))

    def test_edit_add_and_remove_variants(self):
        p = self.created()
        v = p['variants'][0]
        keep = variant(id=v['id'])
        del keep['image_order']
        new = variant(color='Green', image_order=['file:0'])
        resp = self.update(p['id'], {'variants': json.dumps([keep, new]), 'variant_images': [png()]})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(ProductVariant.objects.count(), 2)
        resp = self.update(p['id'], {'variants': json.dumps([new | {'id': resp.data['data']['variants'][1]['id'], 'image_order': None}])})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(list(ProductVariant.objects.values_list('color', flat=True)), ['Green'])

    def test_edit_variant_from_other_product_rejected(self):
        p = self.created()
        other = self.created(model_number='OTHER')
        foreign = variant(id=other['variants'][0]['id'])
        del foreign['image_order']
        resp = self.update(p['id'], {'variants': json.dumps([foreign])})
        self.assertEqual(resp.status_code, 400)

    def test_edit_cover_image_replace_and_remove(self):
        p = self.created(common_image=png('cover.png'))
        self.assertIn('cover', Product.objects.get().common_image.name)
        self.update(p['id'], {'remove_common_image': 'true'})
        self.assertFalse(Product.objects.get().common_image)

    def test_edit_rolls_back_on_error(self):
        p = self.created()
        bad = variant(id=p['variants'][0]['id'], price=-5)
        resp = self.update(p['id'], {'product_name': 'Changed', 'variants': json.dumps([bad])})
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(Product.objects.get().product_name, 'Galaxy S')

    # delete & visibility

    def test_delete_product(self):
        p = self.created()
        resp = self.client.delete(f'/api/v1/products/{p["id"]}/delete/')
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Product.objects.exists())
        self.assertFalse(VariantImage.objects.exists())

    def test_unpublished_products_hidden_from_shoppers_only(self):
        p = self.created(is_published='false')
        anon = APIClient()
        self.assertEqual(anon.get('/api/v1/products/').data['data'], [])
        self.assertEqual(anon.get(f'/api/v1/products/{p["id"]}/').status_code, 404)
        self.assertEqual(len(self.client.get('/api/v1/products/').data['data']), 1)
        self.assertEqual(self.client.get(f'/api/v1/products/{p["id"]}/').status_code, 200)

    def test_admin_listing_includes_variants_and_page_size(self):
        self.created()
        resp = self.client.get('/api/v1/products/?include=variants&page_size=100')
        self.assertEqual(resp.data['data'][0]['variants'][0]['color'], 'Black')
        self.assertNotIn('variants', APIClient().get('/api/v1/products/').data['data'][0])

    def test_dashboard_counts_low_stock_products(self):
        self.created(variants=[variant(stock_quantity=2)])
        resp = self.client.get('/api/v1/products/dashboard-counts/')
        self.assertEqual(resp.data['low_stock_products'], 1)


class VariantDatabaseConstraintTest(TestCase):
    def setUp(self):
        cat = Category.objects.create(category_name='Phones')
        self.product = Product.objects.create(product_name='Phone', brand='Acme', model_number='A1', category=cat)

    def make(self, **kw):
        base = dict(product=self.product, variant_name='V', color='Black', ram_size='8GB', storage_size='128GB', price=100)
        return ProductVariant.objects.create(**{**base, **kw})

    def test_rejects_invalid_prices(self):
        for kw in ({'price': 0}, {'discount_price': 100}, {'discount_price': 0}, {'stock_quantity': 100001}):
            with self.assertRaises(IntegrityError, msg=kw), transaction.atomic():
                self.make(**kw)
        self.make(discount_price=90)

    def test_rejects_duplicate_brand_model(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Product.objects.create(product_name='Phone 2', brand='ACME', model_number='a1', category=self.product.category)
