import traceback
import logging

logger = logging.getLogger(__name__)


class LogErrorsMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_exception(self, request, exception):
        logger.error(
            'Request failed: %s %s\n%s',
            request.method,
            request.path,
            traceback.format_exc(),
        )
        return None
