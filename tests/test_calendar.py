from dataclasses import replace
from datetime import datetime, timedelta
import json

import importlib
import importlib.util
cal = importlib.import_module('multischeduler.calendar') if importlib.util.find_spec('multischeduler.calendar') else None


def test_calendar_module_available():
    assert cal is not None, 'pool-aware calendar feature is missing'
from multischeduler.models import ActivityEvent
from multischeduler import cli, perfectmind


def event(name='Lane Swim', facility='Vicki Keith Pool', hour=12, minutes=60, **kw):
    start = datetime(2026, 10, 25, hour)
    return ActivityEvent('swimming', name, start, start + timedelta(minutes=minutes),
                         location='Artillery Park Aquatic Centre', facility=facility, **kw)


def test_full_swimming_widget_is_unfiltered():
    assert perfectmind.SWIMMING.keyword is None
    assert perfectmind.SWIMMING.widget_id == perfectmind.BADMINTON.widget_id
    assert perfectmind.SWIMMING.source == 'swimming'


def test_both_pools_and_unknown_are_not_guessed():
    assert cal.pool_columns(event(facility='Both Pools')) == ['Vicki Keith Pool', 'Leisure Pool']
    assert cal.pool_columns(event(facility=None)) == ['Unknown']
    assert cal.pool_columns(event(facility='Unidentified water')) == ['Unknown']


def test_classification_keeps_eligibility_separate_from_lanes():
    assert cal.event_record(event('Older Adult Lane Swim'))['suitability'] == 'Dedicated lane swim'
    assert cal.event_record(event('Older Adult Lane Swim'))['age_restrictions'] == 'Not provided; check official details'
    family = cal.event_record(event('Family Swim', 'Leisure Pool'))
    assert family['eligibility'] == 'Adult leisure option'
    assert family['suitability'] != 'Dedicated lane swim'
    assert cal.event_record(event('Parent & Tot Swim'))['eligibility'] == 'Restricted / contextual'
    both = cal.event_record(event('Leisure Swim', 'Both Pools'))
    assert 'does not guarantee dedicated lanes' in both['warning']
    closed = cal.event_record(event(book_button_text='Closed', raw={'AgeRestrictions':'55 to 99'}))
    assert not closed['bookable']
    assert closed['age_restrictions'] == '55 to 99'


def test_exact_overlap_and_touching_boundaries():
    swim = event()
    badminton = replace(event(hour=12, minutes=90), source='badminton', start=datetime(2026,10,25,12,30))
    assert cal.overlap_minutes(swim, badminton) == 30
    assert cal.overlap_minutes(swim, event(hour=13)) == 0


def test_side_by_side_layout_has_no_colliding_rectangles():
    records = [cal.event_record(event(hour=12, minutes=120)), cal.event_record(event(hour=13)), cal.event_record(event(hour=14))]
    laid = cal.layout_blocks(records)
    assert laid[0]['track'] != laid[1]['track']
    assert laid[0]['tracks'] == laid[1]['tracks'] == 2
    assert laid[2]['tracks'] == 1


def test_snapshot_and_standalone_html_are_safe_and_complete(tmp_path):
    events = [event(name='</script><script>alert(1)</script>', raw={'AgeRestrictions':'15 to 99'}), event('Leisure Swim','Both Pools')]
    cal.write_calendar(tmp_path, datetime(2026,10,25), datetime(2026,11,1), events, [])
    snapshot = json.loads((tmp_path/'kingston_calendar.json').read_text())
    assert snapshot['timezone'] == 'America/Toronto'
    assert snapshot['fetched_at'].endswith('-04:00') or snapshot['fetched_at'].endswith('-05:00')
    assert len(snapshot['events']) == 2
    assert snapshot['events'][0]['raw']['AgeRestrictions'] == '15 to 99'
    html = (tmp_path/'kingston_calendar.html').read_text()
    for text in ['date-filter','centre-filter','program-filter','eligibility-filter','Vicki Keith Pool','Leisure Pool','Badminton','overlap','America/Toronto','drop-in-aquatic-programs','Unknown']:
        assert text in html
    assert '</script><script>alert(1)' not in html


def test_official_link_uses_observed_class_structure():
    raw = {'EventId':'example-id', 'OccurrenceDate':'20261025'}
    url = perfectmind.class_url(perfectmind.SWIMMING, raw)
    assert '/Contacts/BookMe4LandingPages/Class?' in url
    assert 'classId=example-id' in url and 'occurrenceDate=20261025' in url
    assert perfectmind.class_url(perfectmind.SWIMMING, {}) is None


def test_calendar_only_skips_ymca_slack_and_pair_reports(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(perfectmind.PerfectMindClient, 'fetch_events', lambda self, calendar, start, end: calls.append(calendar) or [event()])
    def forbidden(*a, **k):
        raise AssertionError('calendar-only must skip this')
    for name in ['fetch_kingston_lap_pool_events','write_html_report','write_markdown_report','_send_slack_if_configured']:
        monkeypatch.setattr(cli, name, forbidden)
    assert cli.main(['--calendar-only','--start-date','2026-10-25','--days','7','--output-dir',str(tmp_path)]) == 0
    assert calls == [perfectmind.SWIMMING, perfectmind.BADMINTON]
    assert (tmp_path/'kingston_calendar.html').exists()


def test_normal_cli_fetches_swimming_once_and_keeps_older_adult_lane(monkeypatch,tmp_path):
    calls, lanes = [], []
    def fetch(self, calendar, start, end):
        calls.append(calendar)
        return [] if calendar == perfectmind.BADMINTON else [event('Older Adult Lane Swim'),event('Family Swim')]
    monkeypatch.setattr(perfectmind.PerfectMindClient,'fetch_events',fetch)
    monkeypatch.setattr(cli,'fetch_kingston_lap_pool_events',lambda *a: [])
    monkeypatch.setattr(cli,'find_nearby_pairs',lambda swim,*a,**k: lanes.extend(swim) or [])
    monkeypatch.setattr(cli,'_send_slack_if_configured',lambda *a:'Slack: skipped by test')
    cli.main(['--start-date','2026-10-25','--output-dir',str(tmp_path)])
    assert calls == [perfectmind.SWIMMING, perfectmind.BADMINTON]
    assert [x.name for x in lanes] == ['Older Adult Lane Swim']
    assert 'kingston_calendar.html' in (tmp_path/'kingston_matches.html').read_text()
