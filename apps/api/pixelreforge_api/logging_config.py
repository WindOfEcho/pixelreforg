from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
import sys
from typing import Any

from .logging_context import get_request_id
from .settings import ApiSettings


STANDARD_LOG_RECORD_KEYS = set(logging.makeLogRecord({}).__dict__.keys())


class RequestContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "request_id"):
            record.request_id = get_request_id()
        if not hasattr(record, "event"):
            record.event = record.getMessage()
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat().replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            "event": getattr(record, "event", record.getMessage()),
        }
        request_id = getattr(record, "request_id", None)
        if request_id is not None:
            payload["request_id"] = request_id

        for key, value in record.__dict__.items():
            if key in STANDARD_LOG_RECORD_KEYS or key in {"event", "request_id"}:
                continue
            payload[key] = _json_safe(value)

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def _json_safe(value: Any) -> Any:
    try:
        json.dumps(value)
        return value
    except TypeError:
        return str(value)


def configure_logging(settings: ApiSettings) -> None:
    level = getattr(logging, settings.log_level, logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(RequestContextFilter())
    if settings.log_format == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)s [%(name)s] request_id=%(request_id)s event=%(event)s %(message)s"
            )
        )

    logging.basicConfig(level=level, handlers=[handler], force=True)
    logging.getLogger("pixelreforge_api").setLevel(level)
    logging.getLogger("uvicorn.error").setLevel(level)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING if settings.log_successful_requests else level)
