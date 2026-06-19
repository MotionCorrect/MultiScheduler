from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import json


@dataclass(frozen=True, slots=True)
class SearchConfig:
    days: int = 7
    max_gap_hours: float = 2.0
    max_distance_km: float | None = None
    max_start_gap_hours: float | None = None
    include_locations: set[str] = field(default_factory=set)
    output_dir: str | None = None
    slack_webhook_url: str | None = None


def load_config(path: Path | None) -> SearchConfig:
    if path is None or not path.exists():
        return SearchConfig()
    data = json.loads(path.read_text(encoding="utf-8"))
    return SearchConfig(
        days=int(data.get("days", 7)),
        max_gap_hours=float(data.get("max_gap_hours", 2.0)),
        max_distance_km=(None if data.get("max_distance_km") is None else float(data["max_distance_km"])),
        max_start_gap_hours=(
            None if data.get("max_start_gap_hours") is None else float(data["max_start_gap_hours"])
        ),
        include_locations={str(item) for item in data.get("include_locations", [])},
        output_dir=data.get("output_dir"),
        slack_webhook_url=data.get("slack_webhook_url"),
    )
