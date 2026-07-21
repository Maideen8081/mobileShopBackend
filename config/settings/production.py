from .base import *

DEBUG = False

ALLOWED_HOSTS = [
    host.strip()
    for host in config(
        "ALLOWED_HOSTS",
        default="mobile-shop-backend.onrender.com,.onrender.com,localhost,127.0.0.1"
    ).split(",")
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

# Cloudflare R2 Storage (only if env vars are set)
R2_BUCKET = config('R2_BUCKET_NAME', default='')
if R2_BUCKET:
    STORAGES = {
        'default': {
            'BACKEND': 'storages.backends.s3boto3.S3Boto3Storage',
        },
        'staticfiles': {
            'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
        },
    }

    AWS_STORAGE_BUCKET_NAME = R2_BUCKET
    AWS_S3_ENDPOINT_URL = config('R2_ENDPOINT_URL', default='')
    AWS_ACCESS_KEY_ID = config('R2_ACCESS_KEY_ID', default='')
    AWS_SECRET_ACCESS_KEY = config('R2_SECRET_ACCESS_KEY', default='')
    AWS_S3_REGION_NAME = 'auto'
    AWS_S3_SIGNATURE_VERSION = 's3v4'
    AWS_DEFAULT_ACL = 'public-read'
    AWS_QUERYSTRING_AUTH = False
    AWS_S3_FILE_OVERWRITE = False
    AWS_S3_ADDRESSING_STYLE = 'path'
    AWS_S3_OBJECT_PARAMETERS = {
        'CacheControl': 'max-age=86400',
    }
