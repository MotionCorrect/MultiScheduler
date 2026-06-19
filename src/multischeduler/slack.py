from __future__ import annotations

from datetime import datetime, timedelta
import json
from pathlib import Path
from urllib.request import Request, urlopen as default_urlopen

from .models import NearbyMatch


def build_slack_payload(
    start: datetime,
    end: datetime,
    matches: list[NearbyMatch],
    output_dir: Path,
    top_n: int = 5,
) -> dict:
    noun = "pairing" if len(matches) == 1 else "pairings"
    lines = [
        f"MultiScheduler found {len(matches)} Kingston activity {noun} for {start:%Y-%m-%d} to {end:%Y-%m-%d}.",
        "",
    ]
    if matches:
        lines.append("Top matches:")
        for index, match in enumerate(matches[:top_n], start=1):
            lines.append(
                f"{index}. {_display_priority_label(match.priority_label)} — "
                f"{match.first.start:%a %b %d %I:%M %p} swim + {match.second.start:%I:%M %p} badminton; "
                f"starts apart {_format_duration(match.start_gap)}; "
                f"overlap {_format_duration(match.overlap)}; "
                f"{_format_spots(match.badminton_spots_available)} badminton spots; "
                f"{_format_distance(match.distance_km)}"
            )
    else:
        lines.append("No matching lane swim + badminton pairings found with the current filters.")
    lines.extend([
        "",
        f"Markdown: {output_dir / 'kingston_matches.md'}",
        f"HTML: {output_dir / 'kingston_matches.html'}",
    ])
    return {"text": "\n".join(lines)}


def post_slack_payload(webhook_url: str, payload: dict, urlopen=default_urlopen, timeout: int = 10) -> None:
    request = Request(
        webhook_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=timeout) as response:
        response.read()


def _display_priority_label(label: str) -> str:
    words = label.replace("_", " ")
    return words[:1].upper() + words[1:]


def _format_duration(duration: timedelta) -> str:
    seconds = int(duration.total_seconds())
    if seconds <= 0:
        return "0m"
    hours, remainder = divmod(seconds, 3600)
    minutes = remainder // 60
    if hours and minutes:
        return f"{hours}h {minutes}m"
    if hours:
        return f"{hours}h"
    return f"{minutes}m"


def _format_spots(spots: int | None) -> str:
    return "unknown" if spots is None else str(spots)


def _format_distance(distance_km: float | None) -> str:
    return "distance n/a" if distance_km is None else f"{distance_km:.1f} km"
