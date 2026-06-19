from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from .models import ActivityEvent, NearbyMatch


def format_event(event: ActivityEvent) -> str:
    time_range = f"{event.start:%a %b %d, %I:%M %p} - {event.end:%I:%M %p}"
    place = ", ".join(part for part in [event.location, event.facility] if part)
    spots = f"; {event.spots}" if event.spots else ""
    button = f"; {event.book_button_text}" if event.book_button_text else ""
    return f"{time_range} — {event.name} ({place}{spots}{button})"


def write_markdown_report(path: Path, start: datetime, end: datetime, lane_events: list[ActivityEvent], badminton_events: list[ActivityEvent], matches: list[NearbyMatch]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# MultiScheduler Kingston Report",
        "",
        f"Window: {start:%Y-%m-%d} to {end:%Y-%m-%d}",
        f"Generated: {datetime.now():%Y-%m-%d %H:%M:%S}",
        "",
        "## Lane Swim + Badminton Within 2 Hours",
        "",
    ]
    if not matches:
        lines.append("- No lane swim / badminton pair found within 2 hours in this window.")
    for match in matches:
        lines.extend([
            f"- Gap: {_format_gap(match.gap)}",
            f"  - Lane swim: {format_event(match.first)}",
            f"  - Badminton: {format_event(match.second)}",
        ])
    lines.extend([
        "",
        "## Source Counts",
        "",
        f"- Lane swim events: {len(lane_events)}",
        f"- Badminton events: {len(badminton_events)}",
        f"- Matched pairs: {len(matches)}",
        "",
        "## Lane Swim Events",
        "",
    ])
    lines.extend([f"- {format_event(event)}" for event in lane_events] or ["- None found."])
    lines.extend(["", "## Badminton Events", ""])
    lines.extend([f"- {format_event(event)}" for event in badminton_events] or ["- None found."])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _format_gap(gap: timedelta) -> str:
    seconds = int(gap.total_seconds())
    if seconds <= 0:
        return "overlap"
    hours, remainder = divmod(seconds, 3600)
    minutes = remainder // 60
    if hours and minutes:
        return f"{hours}h {minutes}m"
    if hours:
        return f"{hours}h"
    return f"{minutes}m"
