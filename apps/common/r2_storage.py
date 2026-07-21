import ssl as _ssl

import botocore.httpsession
from botocore.httpsession import create_urllib3_context as _orig_create_urllib3_context


def _patched_create_urllib3_context(
    ssl_version=None, cert_reqs=None, options=None, ciphers=None
):
    ctx = _orig_create_urllib3_context(
        ssl_version=ssl_version,
        cert_reqs=cert_reqs,
        options=options,
        ciphers=ciphers,
    )
    ctx.minimum_version = _ssl.TLSVersion.TLSv1_2
    ctx.maximum_version = _ssl.TLSVersion.TLSv1_2
    ctx.set_ciphers("DEFAULT:@SECLEVEL=1")
    return ctx


botocore.httpsession.create_urllib3_context = _patched_create_urllib3_context

from storages.backends.s3boto3 import S3Boto3Storage  # noqa: E402
