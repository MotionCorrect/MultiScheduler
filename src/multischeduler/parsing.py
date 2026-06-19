from __future__ import annotations

from datetime import datetime, timedelta

from .models import ActivityEvent


def event_from_perfectmind_class(raw: dict, source: str) -> ActivityEvent:
    date_text = str(raw["OccurrenceDate"])
    start_time = str(raw["FormattedStartTime"])
    end_time = str(raw["FormattedEndTime"])
    start = datetime.strptime(f"{date_text} {start_time}", "%Y%m%d %I:%M %p")
    end = datetime.strptime(f"{date_text} {end_time}", "%Y%m%d %I:%M %p")
    if end < start:
        end = end + timedelta(days=1)
    return ActivityEvent(
        source=source,
        name=str(raw.get("EventName") or ""),
        start=start,
        end=end,
        location=raw.get("Location"),
        facility=raw.get("Facility"),
        spots=raw.get("Spots"),
        book_button_text=raw.get("BookButtonText"),
        course_id=raw.get("CourseId"),
        event_id=raw.get("EventId"),
        raw=raw,
    )
