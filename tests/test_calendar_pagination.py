from datetime import datetime
import pytest
from multischeduler.perfectmind import PerfectMindClient, SWIMMING


def raw(date):
    return dict(EventName='Lane Swim', EventId=date, OccurrenceDate=date,
                FormattedStartTime='12:00 PM', FormattedEndTime='01:00 PM')


def test_pagination_advances_date_like_public_controller(monkeypatch):
    client = PerfectMindClient()
    monkeypatch.setattr(client, '_load_anti_forgery_token', lambda p: 'token')
    requests=[]
    def post(path,payload):
        requests.append(dict(payload))
        if len(requests)==1:
            return dict(classes=[raw('20261025')],nextKey='2026-10-25',classesMaxEndDateString='2026-10-25')
        return dict(classes=[raw('20261026')],nextKey=None)
    monkeypatch.setattr(client,'_post_json',post)
    events=client.fetch_events(SWIMMING,datetime(2026,10,25),datetime(2026,11,1))
    assert requests[1]['dateString']=='2026-10-26'
    assert requests[1]['page'] == '0', 'page is a ten-day offset, not a request counter'
    assert len(events)==2


def test_page_limit_does_not_silently_truncate(monkeypatch):
    client=PerfectMindClient()
    monkeypatch.setattr(client,'_load_anti_forgery_token',lambda p:'token')
    monkeypatch.setattr(client,'_post_json',lambda *a:dict(classes=[raw('20261025')],nextKey='2026-10-25'))
    with pytest.raises(RuntimeError,match='pagination'):
        client.fetch_events(SWIMMING,datetime(2026,10,25),datetime(2026,11,1),max_pages=1)
