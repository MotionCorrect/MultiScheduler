from __future__ import annotations

import argparse
from datetime import datetime, timedelta
from pathlib import Path
import os

from .config import SearchConfig, load_config
from .matching import find_nearby_pairs
from .perfectmind import BADMINTON, SWIMMING, PerfectMindClient
from .calendar import TIMEZONE, write_calendar
from dataclasses import replace
from .reporting import write_html_report, write_markdown_report
from .slack import build_slack_payload, post_slack_payload
from .ymca import fetch_kingston_lap_pool_events

DEFAULT_OUTPUT = Path(os.environ.get("MULTISCHEDULER_OUTPUT_DIR", Path(__file__).resolve().parents[2] / "output"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Cross-reference Kingston lane swim and badminton schedules.")
    parser.add_argument("--config", type=Path, help="Optional JSON search configuration file.")
    parser.add_argument("--days", type=int, help="Upcoming-day window to inspect. Overrides config. Default: 7.")
    parser.add_argument("--max-gap-hours", type=float, help="Maximum allowed gap between activities. Overrides config. Default: 2.")
    parser.add_argument("--max-distance-km", type=float, help="Maximum geographic distance between paired centres.")
    parser.add_argument("--max-start-gap-hours", type=float, help="Require activity start times to be less than this many hours apart.")
    parser.add_argument(
        "--include-location",
        action="append",
        default=[],
        help="Only keep events at this centre/facility. Can be repeated.",
    )
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--slack-webhook-url", help="Optional Slack incoming-webhook URL. Prefer env/config over shell history.")
    parser.add_argument("--start-date", help="Override start date as YYYY-MM-DD for testing.")
    parser.add_argument('--calendar-only', action='store_true', help='Refresh City pool calendar only; skip YMCA, pairing reports and Slack.')
    args = parser.parse_args(argv)

    config = _merge_args(load_config(args.config), args)
    if args.start_date:
        start = datetime.strptime(args.start_date, "%Y-%m-%d")
        end = start + timedelta(days=config.days)
    else:
        start = datetime.now(TIMEZONE).replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=None)
        end = start + timedelta(days=config.days)

    client = PerfectMindClient()
    swimming_events = client.fetch_events(SWIMMING, start, end)
    badminton_events = client.fetch_events(BADMINTON, start, end)
    output_dir = Path(config.output_dir) if config.output_dir else DEFAULT_OUTPUT
    write_calendar(output_dir, start, end, swimming_events, badminton_events)
    print(f"Swimming calendar: {output_dir / 'kingston_calendar.html'} ({len(swimming_events)} swim sessions)")
    print(f"Calendar snapshot: {output_dir / 'kingston_calendar.json'}")
    if args.calendar_only:
        print(f"Badminton events: {len(badminton_events)}; YMCA, pair reports and Slack skipped")
        return 0
    city_lane_events = [replace(e, source='lane_swim') for e in swimming_events if 'lane swim' in e.name.lower()]
    ymca_lane_events = fetch_kingston_lap_pool_events(start, end)
    lane_events = sorted(city_lane_events + ymca_lane_events, key=lambda event: (event.start, event.location or "", event.name))
    matches = find_nearby_pairs(
        lane_events,
        badminton_events,
        max_gap=timedelta(hours=config.max_gap_hours),
        max_distance_km=config.max_distance_km,
        max_start_gap=(None if config.max_start_gap_hours is None else timedelta(hours=config.max_start_gap_hours)),
        include_locations=config.include_locations,
    )

    output_dir = Path(config.output_dir) if config.output_dir else DEFAULT_OUTPUT
    write_markdown_report(output_dir / "kingston_matches.md", start, end, lane_events, badminton_events, matches, config)
    write_html_report(output_dir / "kingston_matches.html", start, end, lane_events, badminton_events, matches, config)
    slack_status = _send_slack_if_configured(config.slack_webhook_url, start, end, matches, output_dir)
    print(f"Lane swim events: {len(lane_events)} ({len(city_lane_events)} City, {len(ymca_lane_events)} YMCA lap pool >2 lanes)")
    print(f"Badminton events: {len(badminton_events)}")
    print(f"Matches within {config.max_gap_hours:g}h: {len(matches)}")
    print(f"Max distance: {'any' if config.max_distance_km is None else f'{config.max_distance_km:g} km'}")
    print(f"Max starts apart: {'any' if config.max_start_gap_hours is None else f'< {config.max_start_gap_hours:g}h'}")
    print(f"Included locations: {'any' if not config.include_locations else ', '.join(sorted(config.include_locations))}")
    print(f"Markdown report: {output_dir / 'kingston_matches.md'}")
    print(f"HTML map report: {output_dir / 'kingston_matches.html'}")
    print(slack_status)
    return 0


def _merge_args(config: SearchConfig, args: argparse.Namespace) -> SearchConfig:
    include_locations = set(config.include_locations)
    include_locations.update(args.include_location or [])
    return SearchConfig(
        days=args.days if args.days is not None else config.days,
        max_gap_hours=args.max_gap_hours if args.max_gap_hours is not None else config.max_gap_hours,
        max_distance_km=args.max_distance_km if args.max_distance_km is not None else config.max_distance_km,
        max_start_gap_hours=(
            args.max_start_gap_hours if args.max_start_gap_hours is not None else config.max_start_gap_hours
        ),
        include_locations=include_locations,
        output_dir=str(args.output_dir) if args.output_dir is not None else config.output_dir,
        slack_webhook_url=(
            args.slack_webhook_url
            or config.slack_webhook_url
            or os.environ.get("MULTISCHEDULER_SLACK_WEBHOOK_URL")
        ),
    )


def _send_slack_if_configured(
    webhook_url: str | None,
    start: datetime,
    end: datetime,
    matches,
    output_dir: Path,
) -> str:
    if not webhook_url:
        return "Slack: not configured"
    try:
        post_slack_payload(webhook_url, build_slack_payload(start, end, matches, output_dir))
    except Exception as exc:  # Keep scheduled scans from failing solely because Slack is down/blocked.
        return f"Slack: failed ({exc})"
    return "Slack: sent"


if __name__ == "__main__":
    raise SystemExit(main())
