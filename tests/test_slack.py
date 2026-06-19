from datetime import datetime, timedelta
from pathlib import Path
import json

from multischeduler.config import SearchConfig, load_config
from multischeduler.models import ActivityEvent, NearbyMatch
from multischeduler.slack import build_slack_payload, post_slack_payload


def test_load_config_accepts_slack_webhook_placeholder(tmp_path) -> None:
    config_path = tmp_path / "multischeduler.json"
    config_path.write_text(
        '{"slack_webhook_url": "https://hooks.slack.com/services/example/example/example"}',
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config.slack_webhook_url == "https://hooks.slack.com/services/example/example/example"


def test_build_slack_payload_summarizes_top_matches() -> None:
    swim = ActivityEvent(
        source="lane_swim",
        name="Lane Swim",
        start=datetime(2026, 6, 20, 12, 50),
        end=datetime(2026, 6, 20, 13, 50),
        location="Artillery Park Aquatic Centre",
    )
    badminton = ActivityEvent(
        source="badminton",
        name="Adult Badminton",
        start=datetime(2026, 6, 20, 12, 45),
        end=datetime(2026, 6, 20, 14, 15),
        location="Rideau Heights Community Centre",
        spots="4 spots left",
    )
    match = NearbyMatch(
        first=swim,
        second=badminton,
        gap=timedelta(0),
        overlap=timedelta(hours=1),
        start_gap=timedelta(minutes=5),
        distance_km=3.4,
        priority_label="best overlap",
        badminton_spots_available=4,
    )

    payload = build_slack_payload(
        datetime(2026, 6, 20),
        datetime(2026, 6, 27),
        [match],
        Path(r"H:\git\MultiScheduler\output"),
    )

    assert payload["text"].startswith("MultiScheduler found 1 Kingston activity pairing")
    assert "4 badminton spots" in payload["text"]
    assert "kingston_matches.html" in payload["text"]


def test_post_slack_payload_uses_incoming_webhook_json() -> None:
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        captured["body"] = json.loads(request.data.decode("utf-8"))
        captured["content_type"] = request.headers["Content-type"]

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return b"ok"

        return Response()

    post_slack_payload("https://hooks.slack.com/services/example", {"text": "hello"}, urlopen=fake_urlopen)

    assert captured == {
        "url": "https://hooks.slack.com/services/example",
        "timeout": 10,
        "body": {"text": "hello"},
        "content_type": "application/json",
    }
