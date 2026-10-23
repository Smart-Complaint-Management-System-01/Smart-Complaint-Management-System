import logging
import time

from django.conf import settings

logger = logging.getLogger("performance")


class ResponseTimeMiddleware:
    """Times every request (NFR-01): adds an X-Response-Time header and logs
    a WARNING for any request slower than SLOW_REQUEST_SECONDS."""

    def __init__(self, get_response):
        self.get_response = get_response
        self.threshold = getattr(settings, "SLOW_REQUEST_SECONDS", 3.0)

    def __call__(self, request):
        start = time.perf_counter()
        response = self.get_response(request)
        elapsed = time.perf_counter() - start
        response["X-Response-Time"] = f"{elapsed * 1000:.0f}ms"

        message = "%s %s -> %s in %.0f ms" % (
            request.method, request.get_full_path(), response.status_code, elapsed * 1000,
        )
        if elapsed > self.threshold:
            logger.warning("SLOW REQUEST: " + message)
        else:
            logger.info(message)
        return response