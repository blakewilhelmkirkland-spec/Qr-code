from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any

from starlette.requests import Request


class JsonLineFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        extra = getattr(record, "extra_fields", None)
        if isinstance(extra, dict):
            payload.update(extra)
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, separators=(",", ":"), default=str)


def configure_logging(level: str) -> None:
    root = logging.getLogger()
    root.handlers.clear()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonLineFormatter())
    root.addHandler(handler)
    root.setLevel(level.upper())


def headers_to_dict(request: Request) -> dict[str, str]:
    # Preserve multi-valued headers by joining with comma
    out: dict[str, str] = {}
    for k, v in request.headers.raw:
        key = k.decode("latin-1").lower()
        val = v.decode("latin-1")
        if key in out:
            out[key] = f"{out[key]}, {val}"
        else:
            out[key] = val
    return out