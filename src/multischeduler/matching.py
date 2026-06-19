from __future__ import annotations

from datetime import datetime, timedelta

from .models import ActivityEvent, NearbyMatch


def upcoming_window(now: datetime | None = None, days: int = 7) -> tuple[datetime, datetime]:
    current = now or datetime.now()
    start = datetime(current.year, current.month, current.day)
    return start, start + timedelta(days=days)


def event_gap(first: ActivityEvent, second: ActivityEvent) -> timedelta:
    if first.end >= second.start and second.end >= first.start:
        return timedelta(0)
    if first.end < second.start:
        return second.start - first.end
    return first.start - second.end


def find_nearby_pairs(
    first_events: list[ActivityEvent],
    second_events: list[ActivityEvent],
    max_gap: timedelta,
) -> list[NearbyMatch]:
    matches: list[NearbyMatch] = []
    for first in first_events:
        for second in second_events:
            if first.start.date() != second.start.date():
                continue
            gap = event_gap(first, second)
            if gap <= max_gap:
                matches.append(NearbyMatch(first=first, second=second, gap=gap))
    return sorted(matches, key=lambda item: (item.first.start, item.gap, item.second.start))
