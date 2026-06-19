from __future__ import annotations

import argparse
from datetime import datetime, timedelta
from pathlib import Path
import os

from .matching import find_nearby_pairs, upcoming_window
from .perfectmind import BADMINTON, LANE_SWIM, PerfectMindClient
from .reporting import write_markdown_report

DEFAULT_OUTPUT = Path(os.environ.get("MULTISCHEDULER_OUTPUT_DIR", r"H:\git\MultiScheduler\output"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Cross-reference Kingston lane swim and badminton schedules.")
    parser.add_argument("--days", type=int, default=7, help="Upcoming-day window to inspect. Default: 7.")
    parser.add_argument("--max-gap-hours", type=float, default=2.0, help="Maximum allowed gap between activities. Default: 2.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--start-date", help="Override start date as YYYY-MM-DD for testing.")
    args = parser.parse_args(argv)

    if args.start_date:
        start = datetime.strptime(args.start_date, "%Y-%m-%d")
        end = start + timedelta(days=args.days)
    else:
        start, end = upcoming_window(days=args.days)

    client = PerfectMindClient()
    lane_events = client.fetch_events(LANE_SWIM, start, end)
    badminton_events = client.fetch_events(BADMINTON, start, end)
    matches = find_nearby_pairs(lane_events, badminton_events, max_gap=timedelta(hours=args.max_gap_hours))

    output_dir = args.output_dir
    write_markdown_report(output_dir / "kingston_matches.md", start, end, lane_events, badminton_events, matches)
    print(f"Lane swim events: {len(lane_events)}")
    print(f"Badminton events: {len(badminton_events)}")
    print(f"Matches within {args.max_gap_hours:g}h: {len(matches)}")
    print(f"Report: {output_dir / 'kingston_matches.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
