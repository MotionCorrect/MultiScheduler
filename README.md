# MultiScheduler

Local scheduler/cross-referencer for City of Kingston recreation calendars.

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
- `output/scheduled_scan.log` when run through the scheduled script

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
