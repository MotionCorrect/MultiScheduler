from datetime import datetime, timedelta

from multischeduler.models import ActivityEvent
from multischeduler.matching import find_nearby_pairs, upcoming_window
from multischeduler.parsing import event_from_perfectmind_class


def test_event_from_perfectmind_class_parses_local_datetime() -> None:
    raw = {
        "EventName": "Lane Swim (Artillery Park Aquatic Centre)",
        "OccurrenceDate": "20260620",
        "FormattedStartTime": "08:00 AM",
        "FormattedEndTime": "08:55 AM",
        "Location": "Artillery Park Aquatic Centre",
        "Facility": "Vicki Keith Pool",
        "Spots": "21 spots left",
        "BookButtonText": "Register",
        "CourseId": "00122416",
    }

    event = event_from_perfectmind_class(raw, source="lane_swim")

    assert event.name == "Lane Swim (Artillery Park Aquatic Centre)"
    assert event.start == datetime(2026, 6, 20, 8, 0)
    assert event.end == datetime(2026, 6, 20, 8, 55)
    assert event.location == "Artillery Park Aquatic Centre"
    assert event.facility == "Vicki Keith Pool"
    assert event.spots == "21 spots left"
    assert event.book_button_text == "Register"


def test_find_nearby_pairs_keeps_events_within_two_hours() -> None:
    swim = ActivityEvent(
        source="lane_swim",
        name="Lane Swim",
        start=datetime(2026, 6, 20, 8, 0),
        end=datetime(2026, 6, 20, 8, 55),
        location="Pool",
    )
    close_badminton = ActivityEvent(
        source="badminton",
        name="Adult Badminton",
        start=datetime(2026, 6, 20, 10, 30),
        end=datetime(2026, 6, 20, 12, 0),
        location="Gym",
    )
    far_badminton = ActivityEvent(
        source="badminton",
        name="Adult Badminton",
        start=datetime(2026, 6, 20, 14, 0),
        end=datetime(2026, 6, 20, 16, 0),
        location="Gym",
    )

    matches = find_nearby_pairs([swim], [close_badminton, far_badminton], max_gap=timedelta(hours=2))

    assert len(matches) == 1
    assert matches[0].first == swim
    assert matches[0].second == close_badminton
    assert matches[0].gap == timedelta(hours=1, minutes=35)


def test_find_nearby_pairs_detects_overlaps_as_zero_gap() -> None:
    swim = ActivityEvent(
        source="lane_swim",
        name="Lane Swim",
        start=datetime(2026, 6, 20, 12, 0),
        end=datetime(2026, 6, 20, 13, 0),
        location="Pool",
    )
    badminton = ActivityEvent(
        source="badminton",
        name="Adult Badminton",
        start=datetime(2026, 6, 20, 12, 30),
        end=datetime(2026, 6, 20, 14, 0),
        location="Gym",
    )

    matches = find_nearby_pairs([swim], [badminton], max_gap=timedelta(hours=2))

    assert len(matches) == 1
    assert matches[0].gap == timedelta(0)


def test_upcoming_window_defaults_to_next_seven_days() -> None:
    start, end = upcoming_window(now=datetime(2026, 6, 19, 2, 0), days=7)

    assert start == datetime(2026, 6, 19)
    assert end == datetime(2026, 6, 26)
