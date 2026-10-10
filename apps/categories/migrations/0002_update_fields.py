from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('categories', '0001_initial'),
    ]

    operations = [
        # The old index name referenced the pre-rename field column. It must be
        # dropped before the field rename rebuilds the table on SQLite, and it is
        # removed on the final model state anyway.
        migrations.RemoveIndex(
            model_name='subcategory',
            name='sub_categor_categor_e70bb6_idx',
        ),
        migrations.RenameField(
            model_name='subcategory',
            old_name='category',
            new_name='parent_category',
        ),
        migrations.AlterModelOptions(
            name='category',
            options={'ordering': ('-created_at',), 'verbose_name_plural': 'Categories'},
        ),
        migrations.AlterModelOptions(
            name='subcategory',
            options={'ordering': ('-created_at',), 'verbose_name_plural': 'Sub Categories'},
        ),
        migrations.RemoveIndex(
            model_name='category',
            name='categories_slug_b4303a_idx',
        ),
        migrations.RemoveIndex(
            model_name='category',
            name='categories_is_acti_aae090_idx',
        ),
        migrations.RemoveField(
            model_name='category',
            name='slug',
        ),
        migrations.AddField(
            model_name='category',
            name='status',
            field=models.CharField(
                choices=[('active', 'Active'), ('inactive', 'Inactive')],
                default='active',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='subcategory',
            name='status',
            field=models.CharField(
                choices=[('active', 'Active'), ('inactive', 'Inactive')],
                default='active',
                max_length=20,
            ),
        ),
        migrations.RunSQL(
            "UPDATE categories SET status = 'active' WHERE is_active = TRUE",
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.RunSQL(
            "UPDATE categories SET status = 'inactive' WHERE is_active = FALSE",
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.RemoveField(
            model_name='category',
            name='is_active',
        ),
        migrations.AddIndex(
            model_name='category',
            index=models.Index(fields=['status'], name='categories_status_idx'),
        ),
        migrations.AddIndex(
            model_name='subcategory',
            index=models.Index(fields=['parent_category'], name='sub_cat_parent_idx'),
        ),
        migrations.AlterField(
            model_name='subcategory',
            name='parent_category',
            field=models.ForeignKey(
                on_delete=models.deletion.CASCADE,
                related_name='sub_categories',
                to='categories.category',
            ),
        ),
    ]
