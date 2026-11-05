from datetime import datetime, timedelta
import json
from pathlib import Path

import pytest

from multischeduler import public_site
from multischeduler.calendar import TIMEZONE


def snapshot(tmp_path, *, age=0, events=None):
    source = tmp_path / 'generated'
    source.mkdir()
    (source / 'kingston_calendar.json').write_text(json.dumps({
        'fetched_at': (datetime.now(TIMEZONE) - timedelta(hours=age)).isoformat(),
        'timezone': 'America/Toronto',
        'events': [{'source': 'swimming'}, {'source': 'badminton'}] if events is None else events,
    }))
    (source / 'kingston_calendar.html').write_text('<html>calendar</html>')
    (source / 'kingston_matches.html').write_text('<html>pairs</html>')
    (source / 'private.log').write_text('not for publication')
    return source


def test_publication_contains_only_allowlisted_files(tmp_path):
    source = snapshot(tmp_path)
    dest = tmp_path / 'site'
    public_site.prepare_site(source, dest)
    assert {p.name for p in dest.iterdir()} == {
        'index.html', 'kingston_calendar.html', 'kingston_calendar.json',
        'kingston_matches.html', '.nojekyll',
    }
    assert (dest / 'index.html').read_bytes() == (source / 'kingston_calendar.html').read_bytes()


@pytest.mark.parametrize('age,events', [(4, None), (0, []), (0, [{'source': 'swimming'}])])
def test_rejects_stale_empty_or_partial_snapshot(tmp_path, age, events):
    source = snapshot(tmp_path, age=age, events=events)
    dest = tmp_path / 'site'
    with pytest.raises(ValueError):
        public_site.prepare_site(source, dest)
    assert not dest.exists()


def test_missing_report_fails_before_publication(tmp_path):
    source = snapshot(tmp_path)
    (source / 'kingston_matches.html').unlink()
    with pytest.raises(ValueError):
        public_site.prepare_site(source, tmp_path / 'site')
    assert not (tmp_path / 'site').exists()
