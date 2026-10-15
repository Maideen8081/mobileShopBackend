"""Prepare existing rows for the constraints added in 0006.

Safe fixes are applied automatically:
  - whitespace in product name / brand / model number is trimmed;
  - a discount price that is 0 or not below the price is cleared (it was never a
    real discount; the storefront already treated 0 as "no discount").
Anything that needs a human decision stops the migration with a list of rows.
"""
import re

from django.db import migrations
from django.db.models import F, Q

MODEL_NUMBER_PATTERN = re.compile(r'^[A-Za-z0-9][A-Za-z0-9 ._/+-]*$')


def check_product_data(apps, schema_editor):
    Product = apps.get_model('products', 'Product')
    ProductVariant = apps.get_model('products', 'ProductVariant')
    problems = []

    ProductVariant.objects.filter(
        Q(discount_price__lte=0) | Q(discount_price__gte=F('price'))
    ).update(discount_price=None)

    seen = {}
    for p in Product.objects.order_by('id'):
        name = ' '.join((p.product_name or '').split())
        brand = ' '.join((p.brand or '').split())
        model = (p.model_number or '').strip()
        if (name, brand, model) != (p.product_name, p.brand, p.model_number):
            p.product_name, p.brand, p.model_number = name, brand, model
            p.save(update_fields=['product_name', 'brand', 'model_number'])
        if len(name) < 2:
            problems.append(f'Product #{p.id}: name "{name}" is shorter than 2 characters')
        if len(brand) < 2:
            problems.append(f'Product #{p.id} "{name}": brand "{brand}" is shorter than 2 characters')
        if not MODEL_NUMBER_PATTERN.match(model):
            problems.append(f'Product #{p.id} "{name}": model number "{model}" has unsupported characters')
        key = (brand.lower(), model.lower())
        if key in seen:
            problems.append(f'Product #{p.id} "{name}" has the same brand and model number as product #{seen[key]}')
        seen.setdefault(key, p.id)

    for v in ProductVariant.objects.filter(Q(price__lte=0) | Q(stock_quantity__gt=100000) | Q(low_stock_alert__gt=1000)):
        problems.append(
            f'Variant #{v.id} of product #{v.product_id}: price must be > 0, stock <= 100000, low stock alert <= 1000'
        )

    if problems:
        raise RuntimeError('Fix these products before migrating:\n  - ' + '\n  - '.join(problems))


class Migration(migrations.Migration):

    dependencies = [
        ('categories', '0005_catalog_constraints'),
        ('products', '0004_product_is_refurbished_and_more'),
    ]

    operations = [
        migrations.RunPython(check_product_data, migrations.RunPython.noop),
    ]
