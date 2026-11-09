"""Performance guard: list endpoints must not issue one query per row (N+1)."""

from decimal import Decimal

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from apps.categories.models import Category, SubCategory
from apps.products.models import Product, ProductVariant


class ProductListQueryBudget(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.category = Category.objects.create(category_name='Phones', status='active')
        self.sub = SubCategory.objects.create(parent_category=self.category, sub_category_name='Smart', status='active')

    def _add(self, n, start=0):
        for i in range(start, start + n):
            p = Product.objects.create(
                product_name=f'Phone {i}', brand='Nova', model_number=f'N{i}',
                category=self.category, sub_category=self.sub,
            )
            for size in ('128', '256'):
                ProductVariant.objects.create(
                    product=p, variant_name=size, color='Black', ram_size='8', storage_size=size,
                    price=Decimal('10000.00'), stock_quantity=3, is_active=True,
                )

    def _queries(self, url):
        with CaptureQueriesContext(connection) as ctx:
            resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        return len(ctx)

    def test_product_list_query_count_does_not_grow_with_rows(self):
        self._add(2)
        small = self._queries('/api/v1/products/')
        self._add(10, start=2)
        large = self._queries('/api/v1/products/')
        self.assertLessEqual(large, small + 1, f'{small} queries for 2 products, {large} for 12')
