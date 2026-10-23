from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('common', '0004_user_google_sub'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='avatar_url',
            field=models.URLField(blank=True, default='', max_length=1024),
        ),
    ]
