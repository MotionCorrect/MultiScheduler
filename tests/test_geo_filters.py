from datetime import datetime, timedelta

from multischeduler.config import SearchConfig, load_config
from multischeduler.geo import haversine_km
from multischeduler.matching import find_nearby_pairs
from multischeduler.models import ActivityEvent
from multischeduler.reporting import write_html_report


def event(source: str, name: str, location: str, lat: float, lon: float) -> ActivityEvent:
    return ActivityEvent(
        source=source,
        name=name,
        start=datetime(2026, 6, 20, 10, 0),
        end=datetime(2026, 6, 20, 11, 0),
        location=location,
        latitude=lat,
        longitude=lon,
    )


def test_haversine_km_estimates_kingston_facility_distance() -> None:
    artillery_park = (44.23448, -76.48408)
    kingston_east = (44.24291, -76.43868)

    distance = haversine_km(*artillery_park, *kingston_east)

    assert 3.5 < distance < 4.2


def test_find_nearby_pairs_can_filter_by_geo_radius() -> None:
    swim = event("lane_swim", "Lane Swim", "Artillery Park", 44.23448, -76.48408)
    close_badminton = event("badminton", "Adult Badminton", "Artillery Park", 44.23448, -76.48408)
    far_badminton = event("badminton", "Adult Badminton", "Kingston East", 44.24291, -76.43868)

    matches = find_nearby_pairs(
        [swim],
        [close_badminton, far_badminton],
        max_gap=timedelta(hours=2),
        max_distance_km=1.0,
    )

    assert len(matches) == 1
    assert matches[0].second.location == "Artillery Park"
    assert matches[0].distance_km == 0


def test_find_nearby_pairs_can_filter_selected_centres() -> None:
    swim = event("lane_swim", "Lane Swim", "Artillery Park Aquatic Centre", 44.23448, -76.48408)
    badminton = event("badminton", "Adult Badminton", "Kingston East Community Centre", 44.24291, -76.43868)

    matches = find_nearby_pairs(
        [swim],
        [badminton],
        max_gap=timedelta(hours=2),
        include_locations={"Artillery Park Aquatic Centre"},
    )

    assert matches == []


def test_find_nearby_pairs_can_filter_by_start_gap() -> None:
    swim = event("lane_swim", "Lane Swim", "Artillery Park", 44.23448, -76.48408)
    starts_soon = ActivityEvent(
        source="badminton",
        name="Starts soon",
        start=datetime(2026, 6, 20, 11, 20),
        end=datetime(2026, 6, 20, 12, 20),
        location="Artillery Park",
        latitude=44.23448,
        longitude=-76.48408,
    )
    starts_too_late = ActivityEvent(
        source="badminton",
        name="Starts too late",
        start=datetime(2026, 6, 20, 11, 31),
        end=datetime(2026, 6, 20, 12, 31),
        location="Artillery Park",
        latitude=44.23448,
        longitude=-76.48408,
    )

    matches = find_nearby_pairs(
        [swim],
        [starts_soon, starts_too_late],
        max_gap=timedelta(hours=2),
        max_start_gap=timedelta(hours=1, minutes=30),
    )

    assert [match.second.name for match in matches] == ["Starts soon"]


def test_load_config_accepts_json_filters(tmp_path) -> None:
    config_path = tmp_path / "multischeduler.json"
    config_path.write_text(
        '{"days": 5, "max_gap_hours": 1.5, "max_distance_km": 2.0, "max_start_gap_hours": 1.5, "include_locations": ["Artillery Park Aquatic Centre"]}',
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config == SearchConfig(
        days=5,
        max_gap_hours=1.5,
        max_distance_km=2.0,
        max_start_gap_hours=1.5,
        include_locations={"Artillery Park Aquatic Centre"},
    )


def test_write_html_report_contains_map_markers_and_filter_metadata(tmp_path) -> None:
    swim = event("lane_swim", "Lane Swim", "Artillery Park Aquatic Centre", 44.23448, -76.48408)
    badminton = event("badminton", "Adult Badminton", "Kingston East Community Centre", 44.24291, -76.43868)
    matches = find_nearby_pairs([swim], [badminton], max_gap=timedelta(hours=2))
    path = tmp_path / "report.html"

    write_html_report(
        path,
        datetime(2026, 6, 20),
        datetime(2026, 6, 27),
        [swim],
        [badminton],
        matches,
        SearchConfig(max_distance_km=5.0, max_start_gap_hours=1.5),
    )

    html = path.read_text(encoding="utf-8")
    assert "leaflet" in html.lower()
    assert "Artillery Park Aquatic Centre" in html
    assert "Kingston East Community Centre" in html
    assert "Max distance: 5.0 km" in html
    assert "Max starts apart: 1.5h" in html
    assert "const matches =" in html
    assert "selectMatch" in html
    assert "Show all pairings" in html
    assert "Pair #1" in html
    assert "Best overlap" in html
    assert "Starts apart" in html
