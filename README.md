# MultiScheduler

Local scheduler/cross-referencer for City of Kingston recreation calendars.

Current job:
- Fetch lane swim events from the City of Kingston PerfectMind swimming calendar.
- Fetch badminton events from the City of Kingston PerfectMind recreation calendar.
- Keep only the upcoming window, default 7 days.
- Report pairs where a lane swim and badminton event happen on the same date within 2 hours of each other.

Run manually:

```bash
uv run multischeduler --days 7 --max-gap-hours 2
```

Output:

- `output/kingston_matches.md`
- `output/scheduled_scan.log` when run through the scheduled script

Credentials:

The current schedule endpoints are readable through PerfectMind's public booking API, so credentials are not copied into this repo. If PerfectMind later requires login, keep credentials outside Git and point automation at the existing external file only.
