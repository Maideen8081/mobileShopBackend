import os

environment = os.getenv('DJANGO_ENV', 'production')

if environment == 'development':
    from .development import *
else:
    from .production import *
