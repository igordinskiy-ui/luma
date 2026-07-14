import logging
import json
import time
import uuid
import re
from collections import Counter
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("kurilka.api")
REQUESTS = Counter()
TOTAL_DURATION_MS = 0
DURATION_BUCKETS_MS = (50, 100, 250, 500, 700, 1000, 2500, 5000)
DURATION_HISTOGRAM = Counter()
REQUEST_ID_PATTERN = re.compile(r"[A-Za-z0-9._:-]{1,128}\Z")


def normalized_request_id(value: str | None) -> str:
    return value if value and REQUEST_ID_PATTERN.fullmatch(value) else str(uuid.uuid4())

class RequestLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = normalized_request_id(request.headers.get("X-Request-ID"))
        request.state.request_id = request_id
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception as exc:
            # Do not log exception messages or tracebacks here: database and
            # provider exceptions may embed user notes, tokens or endpoints.
            logger.error(json.dumps({"event": "request_failed", "request_id": request_id, "method": request.method, "path": request.url.path, "error_type": type(exc).__name__}, ensure_ascii=False))
            raise
        response.headers["X-Request-ID"] = request_id
        duration_ms = int((time.perf_counter() - started) * 1000)
        REQUESTS[str(response.status_code)] += 1
        global TOTAL_DURATION_MS
        TOTAL_DURATION_MS += duration_ms
        for bucket in DURATION_BUCKETS_MS:
            if duration_ms <= bucket:
                DURATION_HISTOGRAM[bucket] += 1
        logger.info(json.dumps({"event": "request_complete", "request_id": request_id, "method": request.method, "path": request.url.path, "status": response.status_code, "duration_ms": duration_ms}, ensure_ascii=False))
        return response


def metrics_text(gauges: dict[str, float | int] | None = None) -> str:
    lines = ["# TYPE kurilka_api_requests_total counter"]
    lines.extend(f'kurilka_api_requests_total{{status="{status}"}} {count}' for status, count in sorted(REQUESTS.items()))
    request_count = sum(REQUESTS.values())
    lines.append("# TYPE kurilka_api_request_duration_ms histogram")
    lines.extend(f'kurilka_api_request_duration_ms_bucket{{le="{bucket}"}} {DURATION_HISTOGRAM[bucket]}' for bucket in DURATION_BUCKETS_MS)
    lines.extend([f'kurilka_api_request_duration_ms_bucket{{le="+Inf"}} {request_count}', f"kurilka_api_request_duration_ms_sum {TOTAL_DURATION_MS}", f"kurilka_api_request_duration_ms_count {request_count}"])
    for name, value in sorted((gauges or {}).items()):
        lines.extend([f"# TYPE {name} gauge", f"{name} {value}"])
    return "\n".join(lines) + "\n"
