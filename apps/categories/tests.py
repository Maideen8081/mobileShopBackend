from django.test import TestCase
from .models import Category, SubCategory


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
