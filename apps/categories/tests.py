import io
import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from PIL import Image
from rest_framework.test import APIClient

from .models import Category, SubCategory

User = get_user_model()
MEDIA_ROOT = tempfile.mkdtemp()


def image_file(name='cat.png', size=(10, 10), fmt='PNG'):
    buf = io.BytesIO()
    Image.new('RGB', size, 'red').save(buf, fmt)
    return SimpleUploadedFile(name, buf.getvalue(), content_type=f'image/{fmt.lower()}')


class CategoryModelTest(TestCase):
    def setUp(self):
        self.category = Category.objects.create(category_name='Smartphones', status='active')

    def test_category_creation(self):
        self.assertEqual(self.category.category_name, 'Smartphones')
        self.assertEqual(self.category.status, 'active')

    def test_category_str(self):
        self.assertEqual(str(self.category), 'Smartphones')

    def test_inactive_status(self):
        cat = Category.objects.create(category_name='Test', status='inactive')
        self.assertEqual(cat.status, 'inactive')


class SubCategoryModelTest(TestCase):
    def setUp(self):
        self.category = Category.objects.create(category_name='Smartphones')
        self.sub = SubCategory.objects.create(
            parent_category=self.category,
            sub_category_name='Android Phones',
            status='active'
        )

    def test_sub_category_creation(self):
        self.assertEqual(self.sub.sub_category_name, 'Android Phones')
        self.assertEqual(self.sub.parent_category, self.category)
        self.assertEqual(self.sub.status, 'active')

    def test_sub_category_str(self):
        self.assertEqual(str(self.sub), 'Android Phones')

    def test_category_relation(self):
        self.assertEqual(self.category.sub_categories.count(), 1)


class CatalogDatabaseConstraintTest(TestCase):
    """The database rejects bad rows even when the API is bypassed."""

    def assertRejected(self, **kwargs):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Category.objects.create(**kwargs)

    def test_category_name_rules(self):
        Category.objects.create(category_name='Audio')
        self.assertRejected(category_name='audio')          # case-insensitive duplicate
        self.assertRejected(category_name='A')              # too short
        self.assertRejected(category_name='x' * 61)         # too long
        self.assertRejected(category_name='Bad<script>')    # unsupported characters
        self.assertRejected(category_name='Phones', status='archived')

    def test_sub_category_unique_per_parent(self):
        a = Category.objects.create(category_name='Phones')
        b = Category.objects.create(category_name='Tablets')
        SubCategory.objects.create(parent_category=a, sub_category_name='Android')
        SubCategory.objects.create(parent_category=b, sub_category_name='Android')  # other parent is fine
        with self.assertRaises(IntegrityError), transaction.atomic():
            SubCategory.objects.create(parent_category=a, sub_category_name='ANDROID')


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class CategoryAPITest(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        self.admin = User.objects.create_user(email='a@example.com', password='Str0ng!Pass', role='admin', is_staff=True)
        self.client = APIClient(raise_request_exception=False)
        self.client.force_login(self.admin)

    def create(self, **data):
        payload = {'category_name': 'Smartphones', 'status': 'active', 'category_image': image_file(), **data}
        payload = {k: v for k, v in payload.items() if v is not None}
        return self.client.post('/api/v1/categories/create/', payload, format='multipart')

    def test_create_category(self):
        resp = self.create(category_name='  Smart   Watches ')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['data']['category_name'], 'Smart Watches')
        self.assertTrue(resp.data['data']['category_image'])

    def test_create_requires_image(self):
        resp = self.create(category_image=None)
        self.assertEqual(resp.status_code, 400)
        self.assertIn('category_image', resp.data)

    def test_create_rejects_bad_names(self):
        for name, field_error in [('', 'blank'), ('A', 'at least 2'), ('x' * 61, 'at most 60'), ('Phones!', 'may only contain')]:
            resp = self.create(category_name=name)
            self.assertEqual(resp.status_code, 400, name)
            self.assertIn(field_error, str(resp.data['category_name']), name)

    def test_create_rejects_duplicate_name_case_insensitive(self):
        self.create(category_name='Audio')
        resp = self.create(category_name='AUDIO')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('already exists', str(resp.data['category_name']))

    def test_create_rejects_non_image_and_large_image(self):
        resp = self.create(category_image=SimpleUploadedFile('x.txt', b'hello', content_type='text/plain'))
        self.assertEqual(resp.status_code, 400)
        big_bytes = image_file('big.png').read() + b'\0' * (2 * 1024 * 1024)
        resp = self.create(category_image=SimpleUploadedFile('big.png', big_bytes, content_type='image/png'))
        self.assertEqual(resp.status_code, 400)

    def test_update_name_status_and_image(self):
        cat_id = self.create().data['data']['id']
        resp = self.client.put(
            f'/api/v1/categories/{cat_id}/',
            {'category_name': 'Phones', 'status': 'inactive', 'category_image': image_file('new.png')},
            format='multipart',
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        cat = Category.objects.get(pk=cat_id)
        self.assertEqual((cat.category_name, cat.status), ('Phones', 'inactive'))
        self.assertIn('new', cat.category_image.name)

    def test_update_keeps_image_when_none_sent_and_refuses_removal(self):
        cat_id = self.create().data['data']['id']
        resp = self.client.put(f'/api/v1/categories/{cat_id}/', {'category_name': 'Phones'}, format='multipart')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(Category.objects.get(pk=cat_id).category_image)
        resp = self.client.put(f'/api/v1/categories/{cat_id}/', {'remove_image': 'true'}, format='multipart')
        self.assertEqual(resp.status_code, 400)

    def test_update_rejects_duplicate_name(self):
        self.create(category_name='Audio')
        cat_id = self.create(category_name='Power').data['data']['id']
        resp = self.client.put(f'/api/v1/categories/{cat_id}/', {'category_name': 'audio'}, format='multipart')
        self.assertEqual(resp.status_code, 400)

    def test_delete_category_with_sub_categories(self):
        cat_id = self.create().data['data']['id']
        SubCategory.objects.create(parent_category_id=cat_id, sub_category_name='Android')
        resp = self.client.delete(f'/api/v1/categories/{cat_id}/')
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Category.objects.filter(pk=cat_id).exists())
        self.assertFalse(SubCategory.objects.exists())

    def test_delete_category_with_products_is_refused(self):
        from apps.products.models import Product
        cat_id = self.create().data['data']['id']
        Product.objects.create(product_name='Phone X', brand='Acme', model_number='X1', category_id=cat_id)
        resp = self.client.delete(f'/api/v1/categories/{cat_id}/')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('1 product', resp.data['message'])
        self.assertTrue(Category.objects.filter(pk=cat_id).exists())

    def test_detail_lists_sub_categories_and_counts(self):
        cat_id = self.create().data['data']['id']
        SubCategory.objects.create(parent_category_id=cat_id, sub_category_name='Android')
        resp = self.client.get(f'/api/v1/categories/{cat_id}/')
        self.assertEqual(resp.data['data']['sub_category_count'], 1)
        self.assertEqual(resp.data['data']['subcategories'][0]['sub_category_name'], 'Android')
        listing = self.client.get('/api/v1/categories/')
        self.assertEqual(listing.data['data'][0]['product_count'], 0)

    def test_inactive_categories_hidden_from_shoppers(self):
        self.create(category_name='Visible')
        self.create(category_name='Hidden', status='inactive')
        public = [c['category_name'] for c in APIClient().get('/api/v1/categories/').data['data']]
        self.assertEqual(public, ['Visible'])
        self.assertEqual(len(self.client.get('/api/v1/categories/').data['data']), 2)

    def test_customer_cannot_write(self):
        customer = APIClient(raise_request_exception=False)
        customer.force_login(User.objects.create_user(email='c@example.com', password='Str0ng!Pass'))
        cat_id = self.create().data['data']['id']
        self.assertEqual(customer.put(f'/api/v1/categories/{cat_id}/', {'status': 'inactive'}).status_code, 403)
        self.assertEqual(customer.delete(f'/api/v1/categories/{cat_id}/').status_code, 403)


class SubCategoryAPITest(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(email='a@example.com', password='Str0ng!Pass', role='admin', is_staff=True)
        self.client = APIClient(raise_request_exception=False)
        self.client.force_login(self.admin)
        self.cat = Category.objects.create(category_name='Phones')

    def create(self, name='Android', parent=None):
        return self.client.post('/api/v1/sub-categories/create/', {
            'parent_category': (parent or self.cat).id, 'sub_category_name': name, 'status': 'active',
        }, format='json')

    def test_create_update_delete(self):
        resp = self.create(' Android  Phones ')
        self.assertEqual(resp.status_code, 201, resp.data)
        sub_id = resp.data['data']['id']
        self.assertEqual(resp.data['data']['sub_category_name'], 'Android Phones')

        resp = self.client.put(f'/api/v1/sub-categories/{sub_id}/', {'sub_category_name': 'iOS'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(SubCategory.objects.get(pk=sub_id).sub_category_name, 'iOS')

        resp = self.client.delete(f'/api/v1/sub-categories/{sub_id}/')
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(SubCategory.objects.exists())

    def test_rejects_duplicate_in_same_parent_only(self):
        self.create('Android')
        self.assertEqual(self.create('android').status_code, 400)
        other = Category.objects.create(category_name='Tablets')
        self.assertEqual(self.create('Android', parent=other).status_code, 201)

    def test_rename_to_existing_name_rejected(self):
        self.create('Android')
        sub_id = self.create('iOS').data['data']['id']
        resp = self.client.put(f'/api/v1/sub-categories/{sub_id}/', {'sub_category_name': 'ANDROID'}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_limit_of_five_per_category(self):
        for i in range(5):
            self.assertEqual(self.create(f'Sub {i}').status_code, 201)
        resp = self.create('Sub 6')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('at most 5', str(resp.data))

    def test_name_rules_and_inactive_parent(self):
        self.assertEqual(self.create('A').status_code, 400)
        self.assertEqual(self.create('Bad$name').status_code, 400)
        inactive = Category.objects.create(category_name='Old', status='inactive')
        self.assertEqual(self.create('Android', parent=inactive).status_code, 400)

    def test_cannot_move_to_other_category(self):
        sub_id = self.create().data['data']['id']
        other = Category.objects.create(category_name='Tablets')
        resp = self.client.put(f'/api/v1/sub-categories/{sub_id}/', {'parent_category': other.id}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_delete_in_use_is_refused(self):
        from apps.products.models import Product
        sub_id = self.create().data['data']['id']
        Product.objects.create(product_name='Phone X', brand='Acme', model_number='X1', category=self.cat, sub_category_id=sub_id)
        resp = self.client.delete(f'/api/v1/sub-categories/{sub_id}/')
        self.assertEqual(resp.status_code, 400)
        self.assertTrue(SubCategory.objects.filter(pk=sub_id).exists())

    def test_list_filter_by_parent_and_product_count(self):
        self.create('Android')
        other = Category.objects.create(category_name='Tablets')
        self.create('iPad', parent=other)
        resp = self.client.get(f'/api/v1/sub-categories/?parent_category={other.id}')
        self.assertEqual([s['sub_category_name'] for s in resp.data['data']], ['iPad'])
        self.assertEqual(resp.data['data'][0]['product_count'], 0)

    def test_customer_cannot_update_or_delete(self):
        sub_id = self.create().data['data']['id']
        customer = APIClient(raise_request_exception=False)
        customer.force_login(User.objects.create_user(email='c@example.com', password='Str0ng!Pass'))
        self.assertEqual(customer.put(f'/api/v1/sub-categories/{sub_id}/', {'sub_category_name': 'X1'}).status_code, 403)
        self.assertEqual(customer.delete(f'/api/v1/sub-categories/{sub_id}/').status_code, 403)
