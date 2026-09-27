from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
import calendar
import re
import shutil
import subprocess
import tempfile
import urllib.parse
import urllib.request

from .models import ActivityEvent

SCHEDULES_URL = "https://eo.ymca.ca/schedules"
KINGSTON_YMCA_LOCATION = "Kingston YMCA"
KINGSTON_YMCA_FACILITY = "Lap Pool"
KINGSTON_YMCA_ADDRESS = "100 Wright Crescent, Kingston"
KINGSTON_YMCA_LATITUDE = 44.2399942
KINGSTON_YMCA_LONGITUDE = -76.5172821

DAY_NAMES = ["MON", "TUES", "WED", "THU", "FRI", "SAT", "SUN"]
WEEKDAY_BY_NAME = {name: index for index, name in enumerate(DAY_NAMES)}
MONTH_BY_NAME = {month.upper(): index for index, month in enumerate(calendar.month_name) if month}


@dataclass(frozen=True, slots=True)
class YmcaLapPoolSlot:
    weekday: int
    start: time
    end: time
    lane_count: int
    activity: str


def fetch_kingston_lap_pool_events(start: datetime, end: datetime) -> list[ActivityEvent]:
    """Fetch the current Kingston YMCA Pools PDF and expand lap-pool lane-swim slots."""
    pdf_url = fetch_kingston_pools_pdf_url()
    with tempfile.TemporaryDirectory(prefix="multischeduler-ymca-") as temp_dir:
        pdf_path = Path(temp_dir) / "kingston_pools.pdf"
        text_path = Path(temp_dir) / "kingston_pools.txt"
        urllib.request.urlretrieve(pdf_url, pdf_path)
        text = extract_pdf_text(pdf_path, text_path)
    return events_from_lap_pool_pdf_text(text, start, end, source_url=pdf_url)


def fetch_kingston_pools_pdf_url(schedules_url: str = SCHEDULES_URL) -> str:
    with urllib.request.urlopen(schedules_url, timeout=30) as response:
        html = response.read().decode("utf-8", "replace")
    kingston_match = re.search(r"<h3[^>]*>\s*<strong>Kingston</strong>.*?(?=<h3[^>]*>)", html, re.IGNORECASE | re.DOTALL)
    scope = kingston_match.group(0) if kingston_match else html
    pools_match = re.search(r'<a\s+href="([^"]+)">\s*Pools\s*</a>', scope, re.IGNORECASE)
    if not pools_match:
        raise RuntimeError("Could not find the Kingston Pools PDF link on the YMCA schedules page")
    return _quote_url(urllib.parse.urljoin(schedules_url, pools_match.group(1)))


def _quote_url(url: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    return urllib.parse.urlunsplit(
        (
            parsed.scheme,
            parsed.netloc,
            urllib.parse.quote(parsed.path, safe="/%"),
            urllib.parse.quote(parsed.query, safe="=&%"),
            parsed.fragment,
        )
    )


def extract_pdf_text(pdf_path: Path, text_path: Path | None = None) -> str:
    text_path = text_path or pdf_path.with_suffix(".txt")
    pdftotext = shutil.which("pdftotext")
    if pdftotext:
        subprocess.run([pdftotext, "-layout", str(pdf_path), str(text_path)], check=True)
        return text_path.read_text(encoding="utf-8", errors="replace")
    raise RuntimeError("pdftotext was not found; install poppler-utils to extract the YMCA Pools PDF")


def events_from_lap_pool_pdf_text(
    text: str,
    start: datetime,
    end: datetime,
    source_url: str | None = None,
) -> list[ActivityEvent]:
    effective_start, effective_end = parse_effective_dates(text)
    slots = parse_lap_pool_slots(text)
    events: list[ActivityEvent] = []
    current = datetime(start.year, start.month, start.day)
    final_day = datetime(end.year, end.month, end.day)
    while current <= final_day:
        current_date = current.date()
        if effective_start <= current_date <= effective_end:
            for slot in slots:
                if slot.weekday != current.weekday():
                    continue
                if slot.lane_count <= 2:
                    continue
                event_start = datetime.combine(current_date, slot.start)
                event_end = datetime.combine(current_date, slot.end)
                if event_end <= event_start:
                    event_end += timedelta(days=1)
                if start <= event_start < end:
                    events.append(_event_from_slot(slot, event_start, event_end, source_url))
        current += timedelta(days=1)
    return sorted(events, key=lambda event: (event.start, event.end, event.name))


def parse_effective_dates(text: str) -> tuple[date, date]:
    normalized = _normalize_text(text)
    match = re.search(
        r"Effective:\s*([A-Za-z]+)\s+(\d{1,2})(?:st|nd|rd|th)?\s*[-–—]\s*([A-Za-z]+)\s+(\d{1,2})(?:st|nd|rd|th)?,\s*(\d{4})",
        normalized,
        re.IGNORECASE,
    )
    if not match:
        raise ValueError("Could not parse the effective date range from the YMCA pool schedule")
    start_month, start_day, end_month, end_day, year = match.groups()
    parsed_year = int(year)
    return (
        date(parsed_year, MONTH_BY_NAME[start_month.upper()], int(start_day)),
        date(parsed_year, MONTH_BY_NAME[end_month.upper()], int(end_day)),
    )


def parse_lap_pool_slots(text: str) -> list[YmcaLapPoolSlot]:
    lap_text = _lap_pool_section(text)
    header_line = next(line for line in lap_text.splitlines() if all(day in line for day in DAY_NAMES))
    starts = [header_line.index(day) for day in DAY_NAMES]
    ends = starts[1:] + [None]
    per_day_lines: dict[str, list[str]] = {day: [] for day in DAY_NAMES}
    seen_header = False
    for line in lap_text.splitlines():
        if not seen_header:
            seen_header = line == header_line
            continue
        if not line.strip():
            for day in DAY_NAMES:
                per_day_lines[day].append("")
            continue
        for day, column_start, column_end in zip(DAY_NAMES, starts, ends):
            per_day_lines[day].append(line[column_start:column_end].rstrip())

    slots: list[YmcaLapPoolSlot] = []
    for day, lines in per_day_lines.items():
        slots.extend(_parse_day_slots(day, lines))
    return sorted(slots, key=lambda slot: (slot.weekday, slot.start, slot.end, slot.lane_count, slot.activity))


def _lap_pool_section(text: str) -> str:
    normalized = _normalize_text(text)
    start_index = normalized.index("Lap Pool Schedule")
    end_candidates = [index for index in (normalized.find("\f", start_index), normalized.find("Leisure Pool Schedule", start_index)) if index != -1]
    end_index = min(end_candidates) if end_candidates else len(normalized)
    return normalized[start_index:end_index]


def _parse_day_slots(day: str, lines: list[str]) -> list[YmcaLapPoolSlot]:
    blocks: list[tuple[str, list[str]]] = []
    current_time: str | None = None
    current_text: list[str] = []
    time_pattern = re.compile(r"(\d{1,2}:\d{2}\s*(?:am|pm)?\s*[-–—]\s*\d{1,2}:\d{2}\s*(?:am|pm))", re.IGNORECASE)
    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        match = time_pattern.search(line)
        if match:
            if current_time is not None:
                blocks.append((current_time, current_text))
            current_time = match.group(1)
            remainder = (line[:match.start()] + " " + line[match.end():]).strip()
            current_text = [remainder] if remainder else []
        elif current_time is not None:
            current_text.append(line)
    if current_time is not None:
        blocks.append((current_time, current_text))

    slots: list[YmcaLapPoolSlot] = []
    for time_range, details in blocks:
        detail_text = " ".join(part for part in details if part).strip()
        lane_match = re.search(r"Lane\s+Swim\s*:\s*(\d+)", detail_text, re.IGNORECASE)
        if not lane_match:
            continue
        activity = re.sub(r"Lane\s+Swim\s*:\s*\d+", "", detail_text, flags=re.IGNORECASE).strip()
        activity = re.sub(r"\s+", " ", activity) or "Lane Swim"
        start_time, end_time = _parse_time_range(time_range)
        slots.append(
            YmcaLapPoolSlot(
                weekday=WEEKDAY_BY_NAME[day],
                start=start_time,
                end=end_time,
                lane_count=int(lane_match.group(1)),
                activity=activity,
            )
        )
    return slots


def _parse_time_range(value: str) -> tuple[time, time]:
    normalized = _normalize_text(value).lower().replace(" ", "")
    match = re.fullmatch(r"(\d{1,2}):(\d{2})(am|pm)?[-–—](\d{1,2}):(\d{2})(am|pm)", normalized)
    if not match:
        raise ValueError(f"Could not parse YMCA time range: {value!r}")
    start_hour_text, start_minute_text, start_suffix, end_hour_text, end_minute_text, end_suffix = match.groups()
    start_hour = int(start_hour_text)
    start_minute = int(start_minute_text)
    end_hour = int(end_hour_text)
    end_minute = int(end_minute_text)
    if start_suffix is None:
        start_suffix = _infer_start_suffix(start_hour, end_hour, end_suffix)
    return (_time_from_12h(start_hour, start_minute, start_suffix), _time_from_12h(end_hour, end_minute, end_suffix))


def _infer_start_suffix(start_hour: int, end_hour: int, end_suffix: str) -> str:
    if end_suffix == "am":
        return "am"
    if start_hour == 12:
        return "pm"
    if start_hour > end_hour:
        return "am"
    return "pm"


def _time_from_12h(hour: int, minute: int, suffix: str) -> time:
    if suffix == "am":
        hour = 0 if hour == 12 else hour
    else:
        hour = 12 if hour == 12 else hour + 12
    return time(hour, minute)


def _event_from_slot(slot: YmcaLapPoolSlot, start: datetime, end: datetime, source_url: str | None) -> ActivityEvent:
    name = "YMCA Lap Pool Lane Swim"
    if slot.activity and slot.activity.lower() != "lane swim":
        name = f"{name} ({slot.activity})"
    raw = {
        "lane_count": slot.lane_count,
        "activity": slot.activity,
        "source_url": source_url,
    }
    return ActivityEvent(
        source="ymca_lap_pool",
        name=name,
        start=start,
        end=end,
        location=KINGSTON_YMCA_LOCATION,
        facility=KINGSTON_YMCA_FACILITY,
        spots=f"{slot.lane_count} lanes",
        latitude=KINGSTON_YMCA_LATITUDE,
        longitude=KINGSTON_YMCA_LONGITUDE,
        address=KINGSTON_YMCA_ADDRESS,
        raw=raw,
    )


def _normalize_text(text: str) -> str:
    return (
        text.replace("\u00a0", " ")
        .replace("\ufffd", "-")
        .replace("�", "-")
        .replace("\u2013", "-")
        .replace("\u2014", "-")
    )
