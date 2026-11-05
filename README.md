# MultiScheduler

Scheduler/cross-referencer for City of Kingston recreation calendars.

**Public calendar:** https://motioncorrect.github.io/MultiScheduler/

## Hosted calendar

GitHub Pages serves a standalone static calendar, plus the pairing/map report and JSON snapshot. No dedicated application server, login, or credentials are required. The GitHub Actions workflow fetches the next seven days and republishes approximately every two hours (at minute 23 UTC), and on pushes or manual dispatch. GitHub scheduled runs can be delayed; always check the visible fetch timestamp. Availability is a snapshot, not a live booking guarantee.

Every build runs tests and rejects missing, empty, incomplete-source, or stale calendar artifacts before deployment. If fetching or validation fails, deployment stops and the last successful site remains online. Workflow results are visible under the repository's Actions tab. Only allowlisted generated reports are published, never logs, local configuration, or browser data. The existing Windows scheduled task is unchanged.

Run the same build locally:

```bash
uv sync --frozen --python 3.11
uv run pytest -q
uv run multischeduler --days 7 --output-dir generated
uv run python -m multischeduler.public_site generated _site
```

Use a fresh `_site` directory for each build. The full build also needs Poppler's `pdftotext` executable for the YMCA PDF (Ubuntu: `sudo apt-get install poppler-utils`; the hosted workflow installs it automatically). Open `_site/index.html` directly or serve it using `python -m http.server --directory _site`.

## License and sources

Application code is MIT licensed; see [LICENSE](LICENSE). Public schedule information remains attributed to the City of Kingston / PerfectMind and Kingston YMCA; the software license does not relicense third-party data, maps, or assets. This is an unofficial tool, not affiliated with those organizations. Confirm eligibility and current availability on the official booking pages; the tool does not reserve places.

Current job:
- Fetch lane swim events from the City of Kingston PerfectMind swimming calendar.
- Fetch badminton events from the City of Kingston PerfectMind recreation calendar.
- Keep only the upcoming window, default 7 days.
- Report pairs where a lane swim and badminton event happen on the same date within 2 hours of each other.

Run manually:

```bash
uv run multischeduler --days 7 --max-gap-hours 2 --max-start-gap-hours 1.5
```

Filter by geography or selected centres:

```bash
# Only pair events within 2 km of each other
uv run multischeduler --days 7 --max-gap-hours 2 --max-distance-km 2

# Only keep pairings whose start times are less than 1.5 hours apart
uv run multischeduler --max-start-gap-hours 1.5

# Only keep events at specific locations/facilities; repeat the flag as needed
uv run multischeduler --include-location "Artillery Park Aquatic Centre" --include-location "Matthew Cahill Gymnasium"

# Or use JSON config (the scheduled task reads multischeduler.config.json)
uv run multischeduler --config multischeduler.example.json
```

Edit `multischeduler.config.json` to change the recurring scan without touching the scheduled task.

Output:

- `output/kingston_matches.md`
- `output/kingston_matches.html` interactive Leaflet/OpenStreetMap view
- `output/kingston_calendar.html` standalone pool-by-pool time-block calendar
- `output/kingston_calendar.json` raw + normalized City events with fetch timestamp and America/Toronto offsets
- `output/scheduled_scan.log` when run through the scheduled script

## Pool-by-pool calendar

```bash
# Focused City refresh: no YMCA fetch, pair-report overwrite, or Slack notification
uv run multischeduler --calendar-only --days 7

# Reproducible date window (inclusive start, exclusive end)
uv run multischeduler --calendar-only --start-date 2026-10-25 --days 7
```

Open `output/kingston_calendar.html` directly; it needs no server, external assets, or JavaScript dependencies. Select a date, centre (Artillery Park by default), program, or eligibility/purpose category. The aligned pool/court blocks split into side-by-side tracks when sessions overlap. Details show source ages, status, spots and official event links; the comparison panel gives exact shared minutes with a selected badminton session, counting Both Pools once. Mobile layouts scroll horizontally rather than squeezing text together.

Normal runs also create this calendar, then retain the existing YMCA lap-pool >2-lanes and lane-swim pairing behavior. City swimming is fetched once from the official **full-schedule widget**; the lane-only subset (including Older Adult Lane Swim) is derived locally. The lane-specific widget silently restricts results server-side even without a client keyword. Calendar filtering is interactive and independent of CLI pairing/geography filters.

**Interpretation:** Vicki Keith Pool and Leisure Pool are distinct. Both Pools appears in both columns but does not guarantee dedicated lanes. Family swim permits adults without children in the leisure pool, not confirmed lap lanes. Parent & tot, older-adult and therapeutic sessions remain contextual/restricted; age values come only from the event response, not assumptions. Unknown facilities remain explicitly Unknown. Closed sessions may link to official details but are not labelled bookable. Registration availability can change after fetch.

**Source limitation:** PerfectMind omits sessions once they have ended, even when querying the same date or a past start date. This is a live upcoming-schedule snapshot, not a full-day historical archive. An earlier run may show already-started closed sessions that disappear after their end time. No screenshot-derived or invented events are inserted. The chosen date remains available even when the API returns no sessions.

Official references: [program descriptions and eligibility](https://www.cityofkingston.ca/activities-and-recreation/aquatics-and-swimming/drop-in-aquatic-programs/) · [Artillery Park facility](https://www.cityofkingston.ca/activities-and-recreation/aquatics-and-swimming/artillery-park-aquatic-centre/). Calendar times use `zoneinfo America/Toronto` (including DST), not the host timezone. `tzdata` supplies Windows timezone data.

Pairing priority:

- Results are filtered by default to starts less than 1.5 hours apart for drop-off/use-the-other-activity scenarios.
- Actual time overlaps appear first, then longer overlaps, then smaller start-time gaps, then smaller event gaps, fewer badminton spots left, and distance.
- Each report shows the priority label, event gap, start-time gap, overlap duration, distance, and badminton spots where available.
- The HTML report includes client-side exploration controls: calendar/date chooser, sort by best fit, sort by fewest badminton spots, sort by closest start times, and sort by closest centres.

Slack notification:

- Optional Slack integration uses an Incoming Webhook URL and sends a short text summary with the top matches plus local report paths.
- Do not commit a real webhook URL. Set `MULTISCHEDULER_SLACK_WEBHOOK_URL` in the scheduled-task environment, pass `--slack-webhook-url` for a one-off test, or set `slack_webhook_url` in a local untracked/private config.
- Slack Enterprise Grid workspaces may require an admin to approve incoming webhooks or the Slack app before messages can post.
- If Slack is unavailable or blocks the webhook, the scan still completes and logs `Slack: failed (...)` instead of failing the schedule run.

Credentials:

The current schedule endpoints are readable through PerfectMind's public booking API, so credentials are not copied into this repo. If PerfectMind later requires login, keep credentials outside Git and point automation at the existing external file only.
