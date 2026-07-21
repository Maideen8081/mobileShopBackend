import ssl as _ssl_mod

try:
    import botocore.httpsession as _bs

    def _get_r2_ssl_context(self):
        ctx = _ssl_mod.SSLContext(_ssl_mod.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname = False
        ctx.verify_mode = _ssl_mod.CERT_NONE
        ctx.minimum_version = _ssl_mod.TLSVersion.TLSv1_2
        ctx.set_ciphers("DEFAULT:@SECLEVEL=1")
        return ctx

    _bs.URLLib3Session._get_ssl_context = _get_r2_ssl_context
except ImportError:
    pass

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
CORS_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in config(
        "CORS_ALLOWED_ORIGINS",
        default="https://mobile-shop-frontend-delta.vercel.app"
    ).split(",")
]

SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
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

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'DEBUG',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'WARNING',
            'propagate': True,
        },
        'boto3': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': False,
        },
        'botocore': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': False,
        },
        'storages': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': False,
        },
    },
}

# Cloudflare R2 Storage (only if env vars are set)
R2_BUCKET = config('R2_BUCKET_NAME', default='')
if R2_BUCKET:
    STORAGES = {
        'default': {
            'BACKEND': 'apps.common.r2_storage.S3Boto3Storage',
        },
        'staticfiles': {
            'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
        },
    }

    R2_PUBLIC_URL = config('R2_PUBLIC_URL', default='').rstrip('/')
    MEDIA_URL = R2_PUBLIC_URL + '/' if R2_PUBLIC_URL else f'https://{R2_BUCKET}.r2.dev/'

    AWS_STORAGE_BUCKET_NAME = R2_BUCKET
    AWS_S3_ENDPOINT_URL = config('R2_ENDPOINT_URL', default='')
    AWS_S3_CUSTOM_DOMAIN = R2_PUBLIC_URL.replace('https://', '') if R2_PUBLIC_URL else f'{R2_BUCKET}.r2.dev'
    AWS_ACCESS_KEY_ID = config('R2_ACCESS_KEY_ID', default='')
    AWS_SECRET_ACCESS_KEY = config('R2_SECRET_ACCESS_KEY', default='')
    AWS_S3_SIGNATURE_VERSION = 's3v4'
    AWS_S3_VERIFY = False
    AWS_QUERYSTRING_AUTH = False
    AWS_S3_FILE_OVERWRITE = False
    AWS_S3_ADDRESSING_STYLE = 'path'
    AWS_S3_OBJECT_PARAMETERS = {
        'CacheControl': 'max-age=86400',
    }
