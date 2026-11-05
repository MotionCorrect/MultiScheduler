"""Validate a fresh generated snapshot, then stage only public report files."""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta
import json
from pathlib import Path
import shutil

from .calendar import TIMEZONE

PUBLIC_FILES = ('kingston_calendar.html', 'kingston_calendar.json', 'kingston_matches.html')


def prepare_site(source: Path, destination: Path) -> None:
    for name in PUBLIC_FILES:
        path = source / name
        if not path.is_file() or not path.stat().st_size:
            raise ValueError(f'Missing or empty public artifact: {name}')
    payload = json.loads((source / 'kingston_calendar.json').read_text(encoding='utf-8'))
    fetched = datetime.fromisoformat(payload['fetched_at'])
    if fetched.tzinfo is None:
        raise ValueError('Snapshot must include a timezone')
    age = datetime.now(TIMEZONE) - fetched
    if not timedelta(minutes=-5) <= age <= timedelta(hours=2):
        raise ValueError('Snapshot is stale or from the future')
    sources = {event['source'] for event in payload['events']}
    if not {'swimming', 'badminton'} <= sources:
        raise ValueError('Snapshot must contain both swimming and badminton')
    if destination.exists():
        raise ValueError('Use a fresh staging directory to avoid publishing unrelated files')
    destination.mkdir(parents=True)
    for name in PUBLIC_FILES:
        shutil.copyfile(source / name, destination / name)
    shutil.copyfile(source / 'kingston_calendar.html', destination / 'index.html')
    (destination / '.nojekyll').touch()
    print(f'Public site ready: {len(payload["events"])} City events; fetched {payload["fetched_at"]}')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('destination', type=Path)
    args = parser.parse_args()
    prepare_site(args.source, args.destination)


if __name__ == '__main__':
    main()
