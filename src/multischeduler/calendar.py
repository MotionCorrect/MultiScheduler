"""Pool-aware public schedule snapshot; no booking or eligibility assumptions."""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
import json
from pathlib import Path
from zoneinfo import ZoneInfo

from .models import ActivityEvent

TIMEZONE = ZoneInfo('America/Toronto')
PROGRAM_SOURCE = 'https://www.cityofkingston.ca/activities-and-recreation/aquatics-and-swimming/drop-in-aquatic-programs/'
FACILITY_SOURCE = 'https://www.cityofkingston.ca/activities-and-recreation/aquatics-and-swimming/artillery-park-aquatic-centre/'


def pool_columns(event: ActivityEvent) -> list[str]:
    if event.source == 'badminton':
        return ['Badminton']
    if (event.facility or '').strip().lower() == 'both pools':
        return ['Vicki Keith Pool', 'Leisure Pool']
    for name in ['Vicki Keith Pool', 'Leisure Pool']:
        if (event.facility or '').strip().lower() == name.lower():
            return [name]
    return ['Unknown']


def event_record(event: ActivityEvent) -> dict:
    record = asdict(event)
    name = event.name.lower()
    dedicated = 'lane swim' in name
    contextual = any(word in name for word in ['older adult', 'therapeutic', 'parent', 'tot'])
    record.update(
        start=event.start.replace(tzinfo=TIMEZONE).isoformat(),
        end=event.end.replace(tzinfo=TIMEZONE).isoformat(),
        date=event.start.date().isoformat(),
        start_minute=event.start.hour * 60 + event.start.minute,
        end_minute=event.end.hour * 60 + event.end.minute + (event.end.date()-event.start.date()).days*1440,
        columns=pool_columns(event),
        program=event.name.split(' (')[0],
        suitability='Dedicated lane swim' if dedicated else 'Not confirmed dedicated lanes',
        eligibility=('Restricted / contextual' if contextual else 'Adult leisure option' if 'family swim' in name else 'Check official details'),
        age_restrictions=(event.raw or {}).get('AgeRestrictions') or 'Not provided; check official details',
        bookable=(event.book_button_text or '').lower() in ['register', 'book', 'book now'],
        warning='Both pools does not guarantee dedicated lanes' if (event.facility or '').lower() == 'both pools' else '',
    )
    return record


def overlap_minutes(first: ActivityEvent, second: ActivityEvent) -> float:
    return max(0, (min(first.end, second.end)-max(first.start, second.start)).total_seconds()/60)


def layout_blocks(records: list[dict]) -> list[dict]:
    """Assign tracks per connected overlap cluster (touching is not overlap)."""
    result, cluster, ends = [], [], []
    for record in sorted(records, key=lambda r: (r['start_minute'], r['end_minute'])):
        if cluster and record['start_minute'] >= max(ends):
            for item in cluster:
                item['tracks'] = len(ends)
            result.extend(cluster)
            cluster, ends = [], []
        track = next((i for i, end in enumerate(ends) if end <= record['start_minute']), len(ends))
        if track == len(ends):
            ends.append(record['end_minute'])
        else:
            ends[track] = record['end_minute']
        cluster.append(dict(record, track=track))
    for item in cluster:
        item['tracks'] = len(ends)
    return result + cluster


def write_calendar(output: Path, start: datetime, end: datetime,
                   swimming: list[ActivityEvent], badminton: list[ActivityEvent]) -> None:
    output.mkdir(parents=True, exist_ok=True)
    payload = dict(timezone='America/Toronto', fetched_at=datetime.now(TIMEZONE).isoformat(),
                   start=start.date().isoformat(), end=end.date().isoformat(),
                   sources=[PROGRAM_SOURCE, FACILITY_SOURCE],
                   events=[event_record(e) for e in swimming + badminton])
    encoded = json.dumps(payload, ensure_ascii=False, default=str, indent=2)
    (output/'kingston_calendar.json').write_text(encoded+'\n', encoding='utf-8')
    template = Path(__file__).with_name('calendar.html').read_text(encoding='utf-8')
    (output/'kingston_calendar.html').write_text(template.replace('__CALENDAR_DATA__', encoded.replace('<', '\\u003c')), encoding='utf-8')
