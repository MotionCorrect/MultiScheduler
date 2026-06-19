from __future__ import annotations

from datetime import datetime, timedelta
from html import escape
import json
from pathlib import Path

from .config import SearchConfig
from .models import ActivityEvent, NearbyMatch


def format_event(event: ActivityEvent) -> str:
    time_range = f"{event.start:%a %b %d, %I:%M %p} - {event.end:%I:%M %p}"
    place = ", ".join(part for part in [event.location, event.facility] if part)
    spots = f"; {event.spots}" if event.spots else ""
    button = f"; {event.book_button_text}" if event.book_button_text else ""
    return f"{time_range} — {event.name} ({place}{spots}{button})"


def write_markdown_report(
    path: Path,
    start: datetime,
    end: datetime,
    lane_events: list[ActivityEvent],
    badminton_events: list[ActivityEvent],
    matches: list[NearbyMatch],
    config: SearchConfig | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    config = config or SearchConfig()
    lines = [
        "# MultiScheduler Kingston Report",
        "",
        f"Window: {start:%Y-%m-%d} to {end:%Y-%m-%d}",
        f"Generated: {datetime.now():%Y-%m-%d %H:%M:%S}",
        f"Max gap: {config.max_gap_hours:g} hours",
        f"Max distance: {_format_optional_distance(config.max_distance_km)}",
        f"Included locations: {_format_locations(config.include_locations)}",
        "",
        f"## Lane Swim + Badminton Within {config.max_gap_hours:g} Hours",
        "",
    ]
    if not matches:
        lines.append("- No lane swim / badminton pair found in this window with the current filters.")
    for match in matches:
        distance = f"; distance: {match.distance_km:.1f} km" if match.distance_km is not None else ""
        lines.extend([
            f"- Gap: {_format_gap(match.gap)}{distance}",
            f"  - Lane swim: {format_event(match.first)}",
            f"  - Badminton: {format_event(match.second)}",
        ])
    lines.extend([
        "",
        "## Source Counts",
        "",
        f"- Lane swim events: {len(lane_events)}",
        f"- Badminton events: {len(badminton_events)}",
        f"- Matched pairs: {len(matches)}",
        "",
        "## Lane Swim Events",
        "",
    ])
    lines.extend([f"- {format_event(event)}" for event in lane_events] or ["- None found."])
    lines.extend(["", "## Badminton Events", ""])
    lines.extend([f"- {format_event(event)}" for event in badminton_events] or ["- None found."])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_html_report(
    path: Path,
    start: datetime,
    end: datetime,
    lane_events: list[ActivityEvent],
    badminton_events: list[ActivityEvent],
    matches: list[NearbyMatch],
    config: SearchConfig | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    config = config or SearchConfig()
    payload = {
        "laneEvents": [_event_payload(event) for event in lane_events],
        "badmintonEvents": [_event_payload(event) for event in badminton_events],
        "matches": [_match_payload(match) for match in matches],
    }
    match_cards = "\n".join(_match_card(match, index) for index, match in enumerate(matches)) or "<p class='empty'>No matches with the current filters.</p>"
    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>MultiScheduler Kingston Map</title>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
  <style>
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; font-family: Inter, Segoe UI, Arial, sans-serif; background: #08111f; color: #e8eef8; }}
    header {{ padding: 24px 28px; background: linear-gradient(135deg, #10213f, #153b4f); border-bottom: 1px solid rgba(255,255,255,.12); }}
    h1 {{ margin: 0 0 8px; font-size: 28px; }}
    .subtitle {{ color: #b7c6da; }}
    .shell {{ display: grid; grid-template-columns: 420px 1fr; min-height: calc(100vh - 112px); }}
    aside {{ overflow: auto; padding: 18px; border-right: 1px solid rgba(255,255,255,.12); background: #0d1728; }}
    #map {{ height: calc(100vh - 112px); min-height: 680px; position: sticky; top: 0; }}
    .filters, .card {{ background: rgba(255,255,255,.06); border: 1px solid rgba(255,255,255,.1); border-radius: 16px; padding: 14px; margin-bottom: 14px; }}
    .metric-row {{ display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-top: 12px; }}
    .metric {{ background: rgba(255,255,255,.08); border-radius: 12px; padding: 10px; }}
    .metric strong {{ display: block; font-size: 22px; }}
    .label {{ color: #93a4bc; font-size: 12px; text-transform: uppercase; letter-spacing: .08em; }}
    .card {{ cursor: pointer; transition: transform .16s, background .16s; }}
    .card:hover {{ transform: translateY(-1px); background: rgba(87, 163, 255, .13); }}
    .gap {{ color: #8fe7c1; font-weight: 700; }}
    .distance {{ color: #ffd480; }}
    .event {{ margin-top: 10px; line-height: 1.35; }}
    .event b {{ color: white; }}
    .empty {{ color: #aab8ca; }}
    .legend {{ position: absolute; z-index: 500; right: 16px; bottom: 20px; background: white; color: #172033; padding: 10px 12px; border-radius: 12px; box-shadow: 0 8px 30px rgba(0,0,0,.18); }}
    .dot {{ display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 6px; }}
    .swim {{ background: #2f80ed; }} .badminton {{ background: #f2994a; }}
    @media (max-width: 900px) {{ .shell {{ grid-template-columns: 1fr; }} #map {{ min-height: 520px; }} }}
  </style>
</head>
<body>
<header>
  <h1>Lane Swim + Badminton Pairings</h1>
  <div class="subtitle">{start:%Y-%m-%d} to {end:%Y-%m-%d} · Max gap: {config.max_gap_hours:g}h · Max distance: {_format_optional_distance(config.max_distance_km)} · Included centres: {_format_locations(config.include_locations)}</div>
</header>
<div class="shell">
  <aside>
    <section class="filters">
      <div class="label">Summary</div>
      <div class="metric-row">
        <div class="metric"><strong>{len(matches)}</strong><span>pairings</span></div>
        <div class="metric"><strong>{len(lane_events)}</strong><span>lane swims</span></div>
        <div class="metric"><strong>{len(badminton_events)}</strong><span>badminton</span></div>
        <div class="metric"><strong>{_format_optional_distance(config.max_distance_km)}</strong><span>radius</span></div>
      </div>
    </section>
    <section>{match_cards}</section>
  </aside>
  <main style="position:relative"><div id="map"></div><div class="legend"><span class="dot swim"></span>Lane swim<br><span class="dot badminton"></span>Badminton</div></main>
</div>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
const matches = {json.dumps(payload, default=str)};
const map = L.map('map').setView([44.235, -76.48], 12);
L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{ maxZoom: 19, attribution: '&copy; OpenStreetMap' }}).addTo(map);
const layers = [];
function marker(event, color) {{
  if (event.latitude == null || event.longitude == null) return null;
  const icon = L.divIcon({{className:'', html:`<div style="width:16px;height:16px;border-radius:50%;background:${{color}};border:3px solid white;box-shadow:0 2px 8px rgba(0,0,0,.35)"></div>`}});
  const m = L.marker([event.latitude, event.longitude], {{icon}}).bindPopup(`<b>${{event.name}}</b><br>${{event.start}} - ${{event.end}}<br>${{event.location || ''}}<br>${{event.spots || ''}}`);
  m.addTo(map); layers.push(m); return m;
}}
matches.laneEvents.forEach(e => marker(e, '#2f80ed'));
matches.badmintonEvents.forEach(e => marker(e, '#f2994a'));
matches.matches.forEach((match, idx) => {{
  if (match.first.latitude != null && match.second.latitude != null) {{
    const line = L.polyline([[match.first.latitude, match.first.longitude], [match.second.latitude, match.second.longitude]], {{color:'#8fe7c1', weight:3, opacity:.55}}).addTo(map);
    layers.push(line);
  }}
}});
if (layers.length) {{ map.fitBounds(L.featureGroup(layers).getBounds().pad(.18)); }}
document.querySelectorAll('[data-match]').forEach(card => card.addEventListener('click', () => {{
  const match = matches.matches[Number(card.dataset.match)];
  if (match?.first?.latitude != null) map.flyTo([match.first.latitude, match.first.longitude], 14);
}}));
</script>
</body>
</html>
"""
    path.write_text(html, encoding="utf-8")


def _match_card(match: NearbyMatch, index: int) -> str:
    distance = f"<span class='distance'>{match.distance_km:.1f} km</span>" if match.distance_km is not None else "<span class='distance'>distance n/a</span>"
    return f"""
    <article class="card" data-match="{index}">
      <div><span class="gap">{escape(_format_gap(match.gap))}</span> · {distance}</div>
      <div class="event"><b>Swim</b><br>{escape(format_event(match.first))}</div>
      <div class="event"><b>Badminton</b><br>{escape(format_event(match.second))}</div>
    </article>
    """


def _event_payload(event: ActivityEvent) -> dict:
    return {
        "source": event.source,
        "name": event.name,
        "start": event.start.strftime("%a %b %d %I:%M %p"),
        "end": event.end.strftime("%I:%M %p"),
        "location": event.location,
        "facility": event.facility,
        "spots": event.spots,
        "latitude": event.latitude,
        "longitude": event.longitude,
    }


def _match_payload(match: NearbyMatch) -> dict:
    return {
        "gap": _format_gap(match.gap),
        "distanceKm": match.distance_km,
        "first": _event_payload(match.first),
        "second": _event_payload(match.second),
    }


def _format_gap(gap: timedelta) -> str:
    seconds = int(gap.total_seconds())
    if seconds <= 0:
        return "overlap"
    hours, remainder = divmod(seconds, 3600)
    minutes = remainder // 60
    if hours and minutes:
        return f"{hours}h {minutes}m"
    if hours:
        return f"{hours}h"
    return f"{minutes}m"


def _format_optional_distance(distance: float | None) -> str:
    return "any" if distance is None else f"{distance:.1f} km"


def _format_locations(locations: set[str]) -> str:
    return "any" if not locations else ", ".join(sorted(locations))
