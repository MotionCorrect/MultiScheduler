from __future__ import annotations

from datetime import datetime, timedelta
import re

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


def event_overlap(first: ActivityEvent, second: ActivityEvent) -> timedelta:
    overlap_start = max(first.start, second.start)
    overlap_end = min(first.end, second.end)
    if overlap_end <= overlap_start:
        return timedelta(0)
    return overlap_end - overlap_start


def event_start_gap(first: ActivityEvent, second: ActivityEvent) -> timedelta:
    return abs(first.start - second.start)


def find_nearby_pairs(
    first_events: list[ActivityEvent],
    second_events: list[ActivityEvent],
    max_gap: timedelta,
    max_distance_km: float | None = None,
    max_start_gap: timedelta | None = None,
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
            overlap = event_overlap(first, second)
            start_gap = event_start_gap(first, second)
            if max_start_gap is not None and start_gap >= max_start_gap:
                continue
            matches.append(
                NearbyMatch(
                    first=first,
                    second=second,
                    gap=gap,
                    distance_km=distance,
                    overlap=overlap,
                    start_gap=start_gap,
                    priority_label=_priority_label(overlap, gap),
                    badminton_spots_available=available_spots(second),
                )
            )
    return sorted(matches, key=_priority_key)


def event_distance_km(first: ActivityEvent, second: ActivityEvent) -> float | None:
    if first.latitude is None or first.longitude is None or second.latitude is None or second.longitude is None:
        return None
    return round(haversine_km(first.latitude, first.longitude, second.latitude, second.longitude), 3)


def available_spots(event: ActivityEvent) -> int | None:
    if not event.spots:
        return None
    match = re.search(r"\d+", event.spots)
    return int(match.group(0)) if match else None


def _priority_key(match: NearbyMatch) -> tuple:
    has_overlap = match.overlap > timedelta(0)
    distance = match.distance_km if match.distance_km is not None else 9999.0
    badminton_spots = match.badminton_spots_available if match.badminton_spots_available is not None else 9999
    return (
        0 if has_overlap else 1,
        -int(match.overlap.total_seconds()),
        int(match.start_gap.total_seconds()),
        int(match.gap.total_seconds()),
        badminton_spots,
        distance,
        match.first.start,
        match.second.start,
    )


def _priority_label(overlap: timedelta, gap: timedelta) -> str:
    if overlap > timedelta(0):
        return "best overlap"
    if gap == timedelta(0):
        return "touching"
    return "nearby gap"


def _location_allowed(event: ActivityEvent, include_locations: set[str] | None) -> bool:
    if not include_locations:
        return True
    event_locations = {event.location, event.facility}
    return any(location in include_locations for location in event_locations if location)
