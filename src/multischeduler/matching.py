from __future__ import annotations

from datetime import datetime, timedelta

from .geo import haversine_km
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
    max_distance_km: float | None = None,
    include_locations: set[str] | None = None,
) -> list[NearbyMatch]:
    matches: list[NearbyMatch] = []
    for first in first_events:
        if not _location_allowed(first, include_locations):
            continue
        for second in second_events:
            if not _location_allowed(second, include_locations):
                continue
            if first.start.date() != second.start.date():
                continue
            gap = event_gap(first, second)
            if gap > max_gap:
                continue
            distance = event_distance_km(first, second)
            if max_distance_km is not None and (distance is None or distance > max_distance_km):
                continue
            matches.append(NearbyMatch(first=first, second=second, gap=gap, distance_km=distance))
    return sorted(matches, key=lambda item: (item.first.start, item.gap, item.distance_km or 0, item.second.start))


def event_distance_km(first: ActivityEvent, second: ActivityEvent) -> float | None:
    if first.latitude is None or first.longitude is None or second.latitude is None or second.longitude is None:
        return None
    return round(haversine_km(first.latitude, first.longitude, second.latitude, second.longitude), 3)


def _location_allowed(event: ActivityEvent, include_locations: set[str] | None) -> bool:
    if not include_locations:
        return True
    event_locations = {event.location, event.facility}
    return any(location in include_locations for location in event_locations if location)
