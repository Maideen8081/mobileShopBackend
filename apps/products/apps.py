from django.apps import AppConfig


class ProductsConfig(AppConfig):
    name = 'apps.products'

    def ready(self):
        from . import signals  # noqa: F401 - registers the back-in-stock receivers
