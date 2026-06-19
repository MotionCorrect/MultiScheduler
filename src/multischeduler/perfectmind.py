from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
import http.cookiejar
import json
import re
import urllib.parse
import urllib.request

from .parsing import event_from_perfectmind_class
from .models import ActivityEvent

BASE_URL = "https://cityofkingston.perfectmind.com"
ANTI_FORGERY_RE = re.compile(r'name="__RequestVerificationToken" type="hidden" value="([^"]+)"')


@dataclass(frozen=True, slots=True)
class PerfectMindCalendar:
    source: str
    page_path: str
    api_path: str
    calendar_id: str
    widget_id: str
    keyword: str | None = None


LANE_SWIM = PerfectMindCalendar(
    source="lane_swim",
    page_path="/24056/Reports/BookMe4BookingPages/Classes?calendarId=54f78b8e-acb8-4585-a237-d9d7d63e0dbf&widgetId=3ff706db-b92a-42a0-96f9-e402cc165685&embed=False&singleCalendarWidget=true",
    api_path="/24056/Reports/BookMe4BookingPagesV2/ClassesV2",
    calendar_id="54f78b8e-acb8-4585-a237-d9d7d63e0dbf",
    widget_id="3ff706db-b92a-42a0-96f9-e402cc165685",
    keyword="lane swim",
)

BADMINTON = PerfectMindCalendar(
    source="badminton",
    page_path="/Contacts/BookMe4BookingPages/Classes?calendarId=401aac5e-a4f3-40bf-a833-91e80a3ba91d&widgetId=15f6af07-39c5-473e-b053-96653f77a406&embed=False",
    api_path="/Contacts/BookMe4BookingPagesV2/ClassesV2",
    calendar_id="401aac5e-a4f3-40bf-a833-91e80a3ba91d",
    widget_id="15f6af07-39c5-473e-b053-96653f77a406",
    keyword="badminton",
)


class PerfectMindClient:
    def __init__(self, base_url: str = BASE_URL, timeout: int = 30) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.cookie_jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cookie_jar))

    def fetch_events(self, calendar: PerfectMindCalendar, start: datetime, end: datetime, max_pages: int = 8) -> list[ActivityEvent]:
        token = self._load_anti_forgery_token(calendar.page_path)
        events: list[ActivityEvent] = []
        page = 0
        after = ""
        while page < max_pages:
            payload = {
                "__RequestVerificationToken": token,
                "calendarId": calendar.calendar_id,
                "widgetId": calendar.widget_id,
                "page": str(page),
                "dateString": start.strftime("%Y-%m-%d"),
                "values": "[]",
                "after": after,
            }
            data = self._post_json(calendar.api_path, payload)
            classes = data.get("classes") or []
            for item in classes:
                if calendar.keyword and calendar.keyword not in str(item.get("EventName", "")).lower():
                    continue
                try:
                    event = event_from_perfectmind_class(item, source=calendar.source)
                except (KeyError, ValueError, TypeError):
                    continue
                if start <= event.start < end:
                    events.append(event)
            next_key = data.get("nextKey")
            if not next_key or not classes:
                break
            # PerfectMind pages are chronological. Stop after the page is past our window.
            latest = max((event_from_perfectmind_class(item, calendar.source).start for item in classes if item.get("FormattedStartTime") and item.get("FormattedEndTime")), default=start)
            if latest >= end:
                break
            after = str(next_key)
            page += 1
        return sorted(events, key=lambda event: (event.start, event.name, event.location or ""))

    def _load_anti_forgery_token(self, page_path: str) -> str:
        html = self._get_text(page_path)
        match = ANTI_FORGERY_RE.search(html)
        if not match:
            raise RuntimeError("PerfectMind anti-forgery token not found on booking page")
        return match.group(1)

    def _get_text(self, path: str) -> str:
        with self.opener.open(self.base_url + path, timeout=self.timeout) as response:
            return response.read().decode("utf-8", "replace")

    def _post_json(self, path: str, payload: dict[str, str]) -> dict:
        body = urllib.parse.urlencode(payload).encode("utf-8")
        request = urllib.request.Request(
            self.base_url + path,
            data=body,
            headers={
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "X-Requested-With": "XMLHttpRequest",
                "Accept": "application/json,text/javascript,*/*;q=0.01",
            },
        )
        with self.opener.open(request, timeout=self.timeout) as response:
            return json.loads(response.read().decode("utf-8"))
