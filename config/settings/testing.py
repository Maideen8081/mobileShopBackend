"""Settings used exclusively for the automated test suite.

Runs against an in-memory SQLite database so the suite can run without a
reachable PostgreSQL server (production uses Neon PostgreSQL). This module is
never used to serve traffic.
"""
from .base import *  # noqa: F401,F403

DEBUG = False

ALLOWED_HOSTS = ['*']

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

# Fast hashing keeps the suite quick; password *policy* is still validated by
# the application validators.
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.MD5PasswordHasher',
]

# Make session/CSRF behaviour deterministic in tests.
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'

CORS_ALLOW_ALL_ORIGINS = True

# Disable throttling interference between tests by default; individual tests
# override REST_FRAMEWORK when they exercise rate limiting.
REST_FRAMEWORK = {
    **REST_FRAMEWORK,  # noqa: F405
    'DEFAULT_THROTTLE_RATES': {
        'anon': '1000/min',
        'user': '1000/min',
        'login': '1000/min',
        'password_reset': '1000/min',
        'register': '1000/min',
    },
}
