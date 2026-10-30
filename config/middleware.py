import logging
import time

from django.conf import settings


performance_logger = logging.getLogger("performance")


class ResponseTimeMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        started_at = time.perf_counter()
        response = self.get_response(request)
        elapsed_ms = (time.perf_counter() - started_at) * 1000

        response["X-Response-Time"] = f"{elapsed_ms:.2f}ms"

        threshold_ms = settings.SLOW_REQUEST_THRESHOLD_SECONDS * 1000
        if elapsed_ms > threshold_ms:
            performance_logger.warning(
                "Slow request: %s %s returned %s in %.2fms (threshold %.2fms)",
                request.method,
                request.path,
                response.status_code,
                elapsed_ms,
                threshold_ms,
            )

        return response
