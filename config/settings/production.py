from datetime import timedelta

from decouple import config

from .base import *

DEBUG = False

ALLOWED_HOSTS = [
    host.strip()
    for host in config("ALLOWED_HOSTS", default=".yourdomain.com").split(",")
]

CORS_ALLOW_ALL_ORIGINS = False

SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True

SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

X_FRAME_OPTIONS = "DENY"

SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"] = timedelta(minutes=15)
SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"] = timedelta(days=7)