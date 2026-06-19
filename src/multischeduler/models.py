from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass(frozen=True, slots=True)
class ActivityEvent:
    source: str
    name: str
    start: datetime
    end: datetime
    location: str | None = None
    facility: str | None = None
    spots: str | None = None
    book_button_text: str | None = None
    course_id: str | None = None
    event_id: str | None = None
    raw: dict | None = None


@dataclass(frozen=True, slots=True)
class NearbyMatch:
    first: ActivityEvent
    second: ActivityEvent
    gap: timedelta
