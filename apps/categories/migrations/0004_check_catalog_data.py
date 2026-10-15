"""Prepare existing rows for the constraints added in 0005.

Safe fixes are applied automatically (trimming/collapsing whitespace in names).
Anything that needs a human decision (a name that is too long, has unsupported
characters, or duplicates another one) stops the migration with a list of the
rows to fix, before any constraint is added.
"""
import re

from django.db import migrations

NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 &'().,/+-]*$")
STATUSES = ('active', 'inactive')


def _name_problem(name):
    if len(name) < 2:
        return 'shorter than 2 characters'
    if len(name) > 60:
        return 'longer than 60 characters'
    if not NAME_PATTERN.match(name):
        return "has characters other than letters, numbers, spaces and & ' ( ) . , / + -"
    return None


def check_catalog_data(apps, schema_editor):
    Category = apps.get_model('categories', 'Category')
    SubCategory = apps.get_model('categories', 'SubCategory')
    problems = []

    seen = {}
    for cat in Category.objects.order_by('id'):
        clean = ' '.join((cat.category_name or '').split())
        updates = []
        if clean != cat.category_name:
            cat.category_name = clean
            updates.append('category_name')
        if cat.status not in STATUSES:
            cat.status = 'inactive'
            updates.append('status')
        if updates:
            cat.save(update_fields=updates)
        if problem := _name_problem(clean):
            problems.append(f'Category #{cat.id} "{clean}": {problem}')
        key = clean.lower()
        if key in seen:
            problems.append(f'Category #{cat.id} "{clean}" duplicates category #{seen[key]} (names are case-insensitive)')
        seen.setdefault(key, cat.id)

    seen = {}
    for sub in SubCategory.objects.order_by('id'):
        clean = ' '.join((sub.sub_category_name or '').split())
        updates = []
        if clean != sub.sub_category_name:
            sub.sub_category_name = clean
            updates.append('sub_category_name')
        if sub.status not in STATUSES:
            sub.status = 'inactive'
            updates.append('status')
        if updates:
            sub.save(update_fields=updates)
        if problem := _name_problem(clean):
            problems.append(f'Sub category #{sub.id} "{clean}": {problem}')
        key = (sub.parent_category_id, clean.lower())
        if key in seen:
            problems.append(f'Sub category #{sub.id} "{clean}" duplicates sub category #{seen[key]} in the same category')
        seen.setdefault(key, sub.id)

    if problems:
        raise RuntimeError(
            'Fix these categories before migrating (rename or merge them in the admin):\n  - '
            + '\n  - '.join(problems)
        )


class Migration(migrations.Migration):

    dependencies = [
        ('categories', '0003_remove_subcategory_sub_categor_categor_e70bb6_idx_and_more'),
    ]

    operations = [
        migrations.RunPython(check_catalog_data, migrations.RunPython.noop),
    ]
