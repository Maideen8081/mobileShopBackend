from .base import *

DEBUG = True
ALLOWED_HOSTS = ['*']
CORS_ALLOW_ALL_ORIGINS = True

# Local dev is served over plain HTTP on localhost, so cookies cannot be
# marked Secure and must use SameSite=Lax (frontend at http://localhost:5173
# and API at http://localhost:8000 are the same site).
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'
