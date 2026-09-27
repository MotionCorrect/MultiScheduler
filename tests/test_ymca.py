from __future__ import annotations

from datetime import datetime, time

from multischeduler.ymca import events_from_lap_pool_pdf_text, parse_effective_dates, parse_lap_pool_slots


PDF_TEXT = """Kingston YMCA // Effective: September 14th - December 19th, 2026

Lap Pool Schedule

MON           TUES              WED           THU                 FRI           SAT               SUN

5:45-8:45am   5:45-8:45am       5:45-8:45am   5:45-8:45am         5:45-8:45am   7:00-8:45am       7:00-8:00am
Lane Swim: 6  Lane Swim: 6      Lane Swim: 6  Lane Swim: 6        Lane Swim: 6  Lane Swim: 6      Lane Swim: 6

10:00-1:00pm  10:00-10:45am     10:00-1:00pm  10:00-10:45am       10:00-1:00pm                    9:00-12:00pm
Public Swim   Public Swim       Public Swim   Public Swim         Public Swim   1:15-3:00 pm      Swimming Lessons
Lane Swim: 4  Lane Swim: 4      Lane Swim: 4  Lane Swim: 4        Lane Swim: 4  Public Swim       Lane Swim: 1
                                                                                Lane Swim: 3
3:30-5:00pm   10:45-10:55am     3:30-5:00pm   10:45-10:55am       3:30-5:00pm                     12:15-3:00pm
Reserved      Lane Swim: 2      Reserved      Lane Swim: 2        Reserved      3:00-4:30pm       Public Swim
                                                                                Public Swim       Lane Swim: 3
5:15-7:30pm   11:00-11:45am     5:15-6:00pm   11:00-11:45am       5:15-7:30pm   Lane Swim: 4
Public Swim   Aquafit           Public Swim   Aquafit             Public Swim                     3:00-4:30pm
Lane Swim: 3                    Lane Swim: 4                      Lane Swim: 4                    Public Swim
              12:00-12:30pm                   12:00-12:30pm                                       Lane Swim: 4
              Deep Water        6:15-7:00pm   Deep Water
              Running           Aquafit       Running
              Lane Swim: 4      Lane Swim: 1  Lane Swim: 4

Leisure Pool Schedule
"""


def test_parse_effective_dates() -> None:
    assert parse_effective_dates(PDF_TEXT) == (
        datetime(2026, 9, 14).date(),
        datetime(2026, 12, 19).date(),
    )


def test_parse_lap_pool_slots_extracts_lane_counts_and_times() -> None:
    slots = parse_lap_pool_slots(PDF_TEXT)
    monday = [slot for slot in slots if slot.weekday == 0]
    assert monday[0].start == time(5, 45)
    assert monday[0].end == time(8, 45)
    assert monday[0].lane_count == 6
    assert any(slot.start == time(17, 15) and slot.lane_count == 3 for slot in monday)

    tuesday = [slot for slot in slots if slot.weekday == 1]
    assert any(slot.start == time(10, 45) and slot.end == time(10, 55) and slot.lane_count == 2 for slot in tuesday)
    assert any(slot.activity == "Deep Water Running" and slot.lane_count == 4 for slot in tuesday)


def test_events_only_include_lap_pool_lane_swim_over_two_lanes() -> None:
    events = events_from_lap_pool_pdf_text(
        PDF_TEXT,
        datetime(2026, 9, 15),
        datetime(2026, 9, 16),
        source_url="https://example.test/pools.pdf",
    )
    assert events
    assert all(event.source == "ymca_lap_pool" for event in events)
    assert all(int(event.spots.split()[0]) > 2 for event in events if event.spots)
    assert not any(event.start.hour == 10 and event.start.minute == 45 for event in events)
    assert any("Deep Water Running" in event.name for event in events)
    assert {event.location for event in events} == {"Kingston YMCA"}
