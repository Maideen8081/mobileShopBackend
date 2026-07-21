import os
import ssl as _ssl

os.environ.setdefault("AWS_CA_BUNDLE", "")

import botocore.httpsession


def _get_r2_ssl_context(self):
    ctx = _ssl.SSLContext(_ssl.PROTOCOL_TLS)
    ctx.check_hostname = False
    ctx.verify_mode = _ssl.CERT_NONE
    ctx.minimum_version = _ssl.TLSVersion.TLSv1_2
    return ctx


botocore.httpsession.URLLib3Session._get_ssl_context = _get_r2_ssl_context

from storages.backends.s3boto3 import S3Boto3Storage  # noqa: E402
