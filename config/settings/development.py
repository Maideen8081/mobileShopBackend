import os

os.environ.setdefault('DB_NAME', 'db.sqlite3')
os.environ.setdefault('DB_USER', '')
os.environ.setdefault('DB_PASSWORD', '')
os.environ.setdefault('DB_HOST', '')
os.environ.setdefault('DB_PORT', '5432')
os.environ.setdefault('SECRET_KEY', 'django-insecure-local-dev-only')

from .base import *  # noqa: E402,F401,F403

DEBUG = True
ALLOWED_HOSTS = ['*']
CORS_ALLOW_ALL_ORIGINS = True

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Local dev is served over plain HTTP on localhost, so cookies cannot be
# marked Secure and must use SameSite=Lax (frontend at http://localhost:5173
# and API at http://localhost:8000 are the same site).
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'

# Print emails (password reset, back-in-stock) to the runserver console unless SMTP is configured in .env.
EMAIL_BACKEND = config('EMAIL_BACKEND', default='django.core.mail.backends.console.EmailBackend')
