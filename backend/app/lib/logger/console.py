"""In-memory log capture for the admin Console page — port of src/lib/logger/console.ts.

Node intercepted global console.log/warn/error. Python instead attaches a
logging.Handler to the root "newsixity" logger tree, so any module using
logging.getLogger(__name__) (or a child of "newsixity") gets captured without
needing to route calls through a custom function.
"""

from __future__ import annotations

import logging
import re
from collections import deque
from dataclasses import dataclass

MAX_LOGS = 100

_REDACT_PATTERNS = [
    (re.compile(r"(authorization:\s*bearer\s+)\S+", re.IGNORECASE), r"\1[REDACTED]"),
    (re.compile(r"(x-newsixity-token[=:]\s*)\S+", re.IGNORECASE), r"\1[REDACTED]"),
    (
        re.compile(r"([\"']?(?:api[_-]?key|token|password|secret)[\"']?\s*[:=]\s*[\"']?)[^\"',\s}]+", re.IGNORECASE),
        r"\1[REDACTED]",
    ),
]


def _redact(message: str) -> str:
    for pattern, replacement in _REDACT_PATTERNS:
        message = pattern.sub(replacement, message)
    return message


@dataclass
class LogEntry:
    timestamp: str
    level: str
    message: str


_recent_logs: deque[LogEntry] = deque(maxlen=MAX_LOGS)

_LEVEL_MAP = {
    logging.DEBUG: "info",
    logging.INFO: "info",
    logging.WARNING: "warn",
    logging.ERROR: "error",
    logging.CRITICAL: "error",
}


class _ConsoleCaptureHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            message = _redact(self.format(record))
            message = re.sub(r"^\[Newsixity\]\s*", "", message)
            level = _LEVEL_MAP.get(record.levelno, "info")
            _recent_logs.appendleft(LogEntry(timestamp=self._timestamp(record), level=level, message=message))
        except Exception:
            pass

    @staticmethod
    def _timestamp(record: logging.LogRecord) -> str:
        from datetime import datetime

        return datetime.fromtimestamp(record.created).strftime("%H:%M:%S")


_installed = False


def install_console_interceptor() -> None:
    global _installed
    if _installed:
        return
    _installed = True

    handler = _ConsoleCaptureHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    logging.getLogger("newsixity").addHandler(handler)


def get_logs() -> list[LogEntry]:
    return list(_recent_logs)
