"""structlog JSON-to-stdout config + request-logging ASGI middleware.

Every request logs method, token-masked path, status, duration_ms, request_id.
Poll endpoints (dashboard/state) log at DEBUG to keep INFO readable.
Tokens are masked to their first 6 characters everywhere.
"""

import logging
import re
import sys
import time
import uuid

import structlog

MASK_VISIBLE_CHARS = 6

_TOKEN_PATH_RE = re.compile(r"^(?P<prefix>(?:/api)?/(?:f|p)/)(?P<token>[^/?]+)")
_POLL_SUFFIXES = ("/dashboard", "/state")


def mask_token(token: str) -> str:
    """Tokens appear in logs as their first 6 characters only."""
    if len(token) <= MASK_VISIBLE_CHARS:
        return token
    return token[:MASK_VISIBLE_CHARS] + "…"


def configure_logging(level: str = "INFO") -> None:
    level_num = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=level_num, force=True)
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level_num),
        logger_factory=structlog.PrintLoggerFactory(sys.stdout),
        cache_logger_on_first_use=False,
    )


def mask_path(path: str) -> str:
    match = _TOKEN_PATH_RE.match(path)
    if match is None:
        return path
    return (
        path[: match.end("prefix")]
        + mask_token(match.group("token"))
        + path[match.end("token") :]
    )


def _is_poll_request(method: str, path: str) -> bool:
    return method == "GET" and path.endswith(_POLL_SUFFIXES)


class RequestLoggingMiddleware:
    """Pure ASGI middleware: request_id binding + one structured line per request."""

    def __init__(self, app):
        self.app = app
        self.logger = structlog.get_logger("helmsman.request")

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = uuid.uuid4().hex[:12]
        structlog.contextvars.bind_contextvars(request_id=request_id)
        start = time.perf_counter()
        status_holder = {"status": 0}

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                status_holder["status"] = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            duration_ms = round((time.perf_counter() - start) * 1000, 1)
            method = scope.get("method", "-")
            path = mask_path(scope.get("path", "-"))
            log = self.logger.debug if _is_poll_request(method, path) else self.logger.info
            log(
                "request",
                method=method,
                path=path,
                status=status_holder["status"],
                duration_ms=duration_ms,
            )
            structlog.contextvars.clear_contextvars()
