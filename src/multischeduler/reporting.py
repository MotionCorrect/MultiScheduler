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
        f"Max starts apart: {_format_optional_hours(config.max_start_gap_hours)}",
        f"Included locations: {_format_locations(config.include_locations)}",
        "",
        f"## Lane Swim + Badminton Within {config.max_gap_hours:g} Hours",
        "",
    ]
    if not matches:
        lines.append("- No lane swim / badminton pair found in this window with the current filters.")
    for match in matches:
        distance = f"; distance: {match.distance_km:.1f} km" if match.distance_km is not None else ""
        overlap = f"; overlap: {_format_gap(match.overlap)}" if match.overlap > timedelta(0) else ""
        spots = f"; badminton spots: {_format_spots(match.badminton_spots_available)}"
        lines.extend([
            f"- {_display_priority_label(match.priority_label)} — gap: {_format_gap(match.gap)}; starts apart: {_format_gap(match.start_gap)}{overlap}{distance}{spots}",
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
    date_options = _date_filter_options(matches)
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
    .card {{ cursor: pointer; transition: transform .16s, background .16s, border-color .16s; }}
    .card:hover {{ transform: translateY(-1px); background: rgba(87, 163, 255, .13); }}
    .card.active {{ background: rgba(143, 231, 193, .14); border-color: #8fe7c1; box-shadow: 0 0 0 1px rgba(143,231,193,.35); }}
    .pair-id {{ display: inline-flex; align-items: center; justify-content: center; width: 26px; height: 26px; border-radius: 999px; margin-right: 8px; background: #8fe7c1; color: #07111e; font-weight: 800; }}
    .controls {{ margin-top: 12px; display:flex; gap: 8px; flex-wrap: wrap; }}
    .control-button {{ border: 1px solid rgba(255,255,255,.18); background: rgba(255,255,255,.08); color: #e8eef8; padding: 8px 10px; border-radius: 10px; cursor: pointer; }}
    select.control-button option {{ color: #172033; background: white; }}
    .control-button:hover {{ background: rgba(255,255,255,.14); }}
    .chooser-label {{ color:#93a4bc; font-size: 12px; align-self:center; }}
    .focus-note {{ color:#93a4bc; font-size: 13px; margin-top: 8px; }}
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
  <a href="kingston_calendar.html" style="color:#8fe7c1">Pool-by-pool time-block calendar →</a>
  <div class="subtitle">{start:%Y-%m-%d} to {end:%Y-%m-%d} · Max gap: {config.max_gap_hours:g}h · Max distance: {_format_optional_distance(config.max_distance_km)} · Max starts apart: {_format_optional_hours(config.max_start_gap_hours)} · Included centres: {_format_locations(config.include_locations)}</div>
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
      <div class="controls">
        <label class="chooser-label" for="date-filter">Calendar</label>
        <select class="control-button" id="date-filter">{date_options}</select>
        <label class="chooser-label" for="sort-filter">Sort by</label>
        <select class="control-button" id="sort-filter">
          <option value="priority">Best drop-off fit</option>
          <option value="spots">Fewest badminton spots</option>
          <option value="start-gap">Closest start times</option>
          <option value="distance">Closest centres</option>
        </select>
        <button class="control-button" id="show-all">Show all pairings</button>
      </div>
      <div class="focus-note">Use the calendar chooser and sort menu to explore. Click a card to isolate that pair: only its two markers and connector stay bright, and the map fits both locations.</div>
    </section>
    <section id="match-list">{match_cards}</section>
  </aside>
  <main style="position:relative"><div id="map"></div><div class="legend"><span class="dot swim"></span>Lane swim<br><span class="dot badminton"></span>Badminton</div></main>
</div>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
const matches = {json.dumps(payload, default=str)};
const map = L.map('map').setView([44.235, -76.48], 12);
L.tileLayer('https://{{s}}.tile.openstreetmap.fr/hot/{{z}}/{{x}}/{{y}}.png', {{
  maxZoom: 19,
  subdomains: 'abc',
  attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors, Tiles courtesy of <a href="https://www.hotosm.org/">HOT</a>'
}}).addTo(map);
const allLayers = [];
let focusLayers = [];
function pointIcon(color, label = '', size = 18, opacity = 1) {{
  const labelHtml = label ? `<span style="position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);font:800 11px/1 sans-serif;color:#07111e">${{label}}</span>` : '';
  return L.divIcon({{className:'', html:`<div style="position:relative;width:${{size}}px;height:${{size}}px;border-radius:50%;background:${{color}};opacity:${{opacity}};border:3px solid white;box-shadow:0 2px 8px rgba(0,0,0,.35)">${{labelHtml}}</div>`}});
}}
function marker(event, color, opacity = .42) {{
  if (event.latitude == null || event.longitude == null) return null;
  const m = L.marker([event.latitude, event.longitude], {{icon: pointIcon(color, '', 14, opacity)}}).bindPopup(`<b>${{event.name}}</b><br>${{event.start}} - ${{event.end}}<br>${{event.location || ''}}<br>${{event.spots || ''}}`);
  m.addTo(map); allLayers.push(m); return m;
}}
function eventPopup(event, title) {{
  return `<b>${{title}}</b><br>${{event.name}}<br>${{event.start}} - ${{event.end}}<br>${{event.location || ''}}<br>${{event.facility || ''}}<br>${{event.spots || ''}}`;
}}
function clearFocus() {{
  focusLayers.forEach(layer => map.removeLayer(layer));
  focusLayers = [];
  document.querySelectorAll('[data-match]').forEach(card => card.classList.remove('active'));
}}
function showAllPairings() {{
  clearFocus();
  document.querySelector('#date-filter').value = 'all';
  document.querySelector('#sort-filter').value = 'priority';
  applyExplorationFilters(false);
  allLayers.forEach(layer => {{ if (!map.hasLayer(layer)) layer.addTo(map); }});
  if (allLayers.length) map.fitBounds(L.featureGroup(allLayers).getBounds().pad(.18));
}}
function visibleCards() {{ return [...document.querySelectorAll('[data-match]')].filter(card => card.style.display !== 'none'); }}
function applyExplorationFilters(selectFirst = true) {{
  const date = document.querySelector('#date-filter')?.value || 'all';
  const sort = document.querySelector('#sort-filter')?.value || 'priority';
  const cards = [...document.querySelectorAll('[data-match]')];
  cards.forEach(card => {{ card.style.display = (date === 'all' || card.dataset.date === date) ? '' : 'none'; }});
  const ordered = visibleCards().sort((a, b) => {{
    const ma = matches.matches[Number(a.dataset.match)];
    const mb = matches.matches[Number(b.dataset.match)];
    if (sort === 'spots') return (ma.badmintonSpotsAvailable ?? 9999) - (mb.badmintonSpotsAvailable ?? 9999);
    if (sort === 'start-gap') return ma.startGapMinutes - mb.startGapMinutes;
    if (sort === 'distance') return (ma.distanceKm ?? 9999) - (mb.distanceKm ?? 9999);
    return Number(a.dataset.match) - Number(b.dataset.match);
  }});
  const container = document.querySelector('#match-list');
  ordered.forEach(card => container.appendChild(card));
  if (selectFirst && ordered.length) selectMatch(Number(ordered[0].dataset.match));
}}
function selectMatch(index) {{
  const match = matches.matches[index];
  if (!match) return;
  clearFocus();
  allLayers.forEach(layer => layer.setOpacity?.(.18));
  const bounds = [];
  const pairNo = String(index + 1);
  if (match.first.latitude != null) {{
    const swim = L.marker([match.first.latitude, match.first.longitude], {{icon: pointIcon('#2f80ed', pairNo, 30, 1), zIndexOffset: 1000}}).bindPopup(eventPopup(match.first, `Pair #${{pairNo}} swim`)).addTo(map);
    focusLayers.push(swim); bounds.push([match.first.latitude, match.first.longitude]);
  }}
  if (match.second.latitude != null) {{
    const badminton = L.marker([match.second.latitude, match.second.longitude], {{icon: pointIcon('#f2994a', pairNo, 30, 1), zIndexOffset: 1000}}).bindPopup(eventPopup(match.second, `Pair #${{pairNo}} badminton`)).addTo(map);
    focusLayers.push(badminton); bounds.push([match.second.latitude, match.second.longitude]);
  }}
  if (bounds.length === 2) {{
    const line = L.polyline(bounds, {{color:'#8fe7c1', weight:7, opacity:.95, dashArray:'10 8'}}).addTo(map);
    focusLayers.push(line);
    map.fitBounds(L.latLngBounds(bounds).pad(.55));
  }} else if (bounds.length === 1) {{
    map.flyTo(bounds[0], 14);
  }}
  document.querySelector(`[data-match="${{index}}"]`)?.classList.add('active');
}}
matches.laneEvents.forEach(e => marker(e, '#2f80ed'));
matches.badmintonEvents.forEach(e => marker(e, '#f2994a'));
matches.matches.forEach((match, idx) => {{
  if (match.first.latitude != null && match.second.latitude != null) {{
    const line = L.polyline([[match.first.latitude, match.first.longitude], [match.second.latitude, match.second.longitude]], {{color:'#8fe7c1', weight:2, opacity:.18}}).addTo(map);
    allLayers.push(line);
  }}
}});
if (allLayers.length) {{ map.fitBounds(L.featureGroup(allLayers).getBounds().pad(.18)); }}
document.querySelectorAll('[data-match]').forEach(card => card.addEventListener('click', () => selectMatch(Number(card.dataset.match))));
document.querySelector('#show-all')?.addEventListener('click', showAllPairings);
document.querySelector('#date-filter')?.addEventListener('change', () => applyExplorationFilters(true));
document.querySelector('#sort-filter')?.addEventListener('change', () => applyExplorationFilters(true));
if (matches.matches.length) applyExplorationFilters(true);
</script>
</body>
</html>
"""
    path.write_text(html, encoding="utf-8")


def _match_card(match: NearbyMatch, index: int) -> str:
    distance = f"<span class='distance'>{match.distance_km:.1f} km</span>" if match.distance_km is not None else "<span class='distance'>distance n/a</span>"
    overlap = f" · Overlap {_format_gap(match.overlap)}" if match.overlap > timedelta(0) else ""
    return f"""
    <article class="card" data-match="{index}" data-date="{match.first.start:%Y-%m-%d}" aria-label="Pair #{index + 1}">
      <div><span class="pair-id">{index + 1}</span><span class="gap">{escape(_display_priority_label(match.priority_label))}</span> · {distance}</div>
      <div class="focus-note">Gap {_format_gap(match.gap)} · Starts apart {_format_gap(match.start_gap)}{overlap} · Badminton spots {_format_spots(match.badminton_spots_available)}</div>
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
        "overlap": _format_gap(match.overlap),
        "startGap": _format_gap(match.start_gap),
        "priorityLabel": _display_priority_label(match.priority_label),
        "date": match.first.start.strftime("%Y-%m-%d"),
        "startGapMinutes": int(match.start_gap.total_seconds() // 60),
        "badmintonSpotsAvailable": match.badminton_spots_available,
        "distanceKm": match.distance_km,
        "first": _event_payload(match.first),
        "second": _event_payload(match.second),
    }


def _date_filter_options(matches: list[NearbyMatch]) -> str:
    dates = sorted({match.first.start.date() for match in matches})
    options = ['<option value="all">All dates</option>']
    options.extend(
        f'<option value="{date:%Y-%m-%d}">{date:%a %b %d}</option>'
        for date in dates
    )
    return "\n".join(options)


def _format_spots(spots: int | None) -> str:
    return "n/a" if spots is None else str(spots)


def _display_priority_label(label: str) -> str:
    words = label.replace("_", " ")
    return words[:1].upper() + words[1:]


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


def _format_optional_hours(hours: float | None) -> str:
    return "any" if hours is None else f"{hours:g}h"


def _format_locations(locations: set[str]) -> str:
    return "any" if not locations else ", ".join(sorted(locations))
