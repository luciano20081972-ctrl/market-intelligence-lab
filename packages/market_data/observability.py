from __future__ import annotations

import json
import logging
import re
import time
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import Request, Response

SECRET_PATTERN = re.compile(
    r"(?i)(authorization|api[_-]?key|token|password|secret)(\s*[=:]\s*)([^,\s]+)"
)


def redact(value: str) -> str:
    return SECRET_PATTERN.sub(lambda match: f"{match.group(1)}{match.group(2)}[REDACTED]", value)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return json.dumps(
            {
                "timestamp": self.formatTime(record),
                "level": record.levelname,
                "logger": record.name,
                "message": redact(record.getMessage()),
            },
            separators=(",", ":"),
        )


def configure_logging(*, json_output: bool = False, level: int = logging.INFO) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(
        JsonFormatter() if json_output else logging.Formatter("%(levelname)s %(name)s %(message)s")
    )
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)


async def correlation_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    correlation_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))[:128]
    began = time.perf_counter()
    response = await call_next(request)
    duration_ms = int((time.perf_counter() - began) * 1000)
    response.headers["X-Correlation-ID"] = correlation_id
    response.headers["X-Request-Duration-Ms"] = str(duration_ms)
    return response


def operational_log(logger: logging.Logger, event: str, **fields: Any) -> None:
    safe = {key: redact(str(value)) for key, value in fields.items()}
    logger.info("%s %s", event, json.dumps(safe, sort_keys=True, separators=(",", ":")))
