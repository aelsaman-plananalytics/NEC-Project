"""
Security hardening middleware (API layer only).
Request size limit, rate limiting, API key, audit log.
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, JSONResponse

from app.api_errors import structured_error_response, BAD_REQUEST, REQUEST_TOO_LARGE, RATE_LIMIT_EXCEEDED, UNAUTHORIZED
from app.security_config import (
    REQUEST_SIZE_LIMIT_BYTES,
    REQUIRE_API_KEY,
    get_valid_api_keys,
)
from app.rate_limit import check_rate_limit
from app.api_audit import log_api_request


def _client_ip(request: Request) -> str:
    """Client IP from X-Forwarded-For or request.client."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host or "unknown"
    return "unknown"


def _is_api_route(request: Request) -> bool:
    path = (request.scope.get("path") or "").strip()
    return path.startswith("/api/")


def _is_validate_programme_route(request: Request) -> bool:
    path = (request.scope.get("path") or "").strip()
    return "/validate_programme" in path


class SecurityMiddleware(BaseHTTPMiddleware):
    """Enforce request size limit, rate limit, API key; audit log."""

    async def dispatch(self, request: Request, call_next) -> Response:
        if not _is_api_route(request):
            return await call_next(request)
        # Allow CORS preflight to pass through without auth/rate-limit gates.
        # CORSMiddleware will generate the correct preflight response.
        if (request.method or "").upper() == "OPTIONS":
            return await call_next(request)

        # 1. Request size limit (Content-Length)
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > REQUEST_SIZE_LIMIT_BYTES:
                    return structured_error_response(
                        413,
                        REQUEST_TOO_LARGE,
                        "Request body exceeds maximum allowed size.",
                        details={"max_bytes": REQUEST_SIZE_LIMIT_BYTES},
                    )
            except ValueError:
                pass

        # 2. API key (when required)
        if REQUIRE_API_KEY:
            key = (request.headers.get("x-api-key") or "").strip()
            valid = get_valid_api_keys()
            if not valid:
                return structured_error_response(
                    401,
                    UNAUTHORIZED,
                    "API key required but none configured.",
                    details=None,
                )
            if not key or key not in valid:
                return structured_error_response(
                    401,
                    UNAUTHORIZED,
                    "Invalid or missing API key.",
                    details=None,
                )

        # 3. Rate limit
        ip = _client_ip(request)
        allowed, count = check_rate_limit(ip)
        if not allowed:
            return structured_error_response(
                429,
                RATE_LIMIT_EXCEEDED,
                "Rate limit exceeded. Try again later.",
                details={"requests_this_minute": count},
            )

        response = await call_next(request)

        # 4. Audit log (skip validate_programme; endpoint logs with response_signature)
        if not _is_validate_programme_route(request):
            route = request.scope.get("path") or "-"
            idem = (request.headers.get("idempotency-key") or "").strip() or "-"
            log_api_request(
                ip=ip,
                route=route,
                status_code=response.status_code,
                idempotency_key=idem if idem != "-" else None,
                response_signature=None,
            )

        return response
