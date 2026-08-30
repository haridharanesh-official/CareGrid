from __future__ import annotations

import threading
from collections import deque
from typing import Any

from .database import utc_now


_lock = threading.Lock()
_sequence = 0
_events: deque[dict[str, Any]] = deque(maxlen=250)


def publish_event(event_type: str, data: dict[str, Any]) -> dict[str, Any]:
    global _sequence
    with _lock:
        _sequence += 1
        event = {"sequence": _sequence, "type": event_type, "timestamp": utc_now(), "data": data}
        _events.append(event)
        return dict(event)


def events_after(sequence: int) -> list[dict[str, Any]]:
    with _lock:
        return [dict(event) for event in _events if event["sequence"] > sequence]
