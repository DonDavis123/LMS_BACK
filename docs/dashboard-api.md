# Dashboard API

Why: the dashboard used to build its numbers from ~15 list requests (a total, a
previous-window count, one count per lead status, and up to 6 pages of leads),
and repeated all of them on every 7d / 30d / 90d click. One aggregated call
replaces them.

## `GET /api/dashboard/stats/`

Auth: JWT, company user, same permission as the leads list (admin / superadmin).

| Query param | Default | Notes |
|---|---|---|
| `range` | `30` | Whole days, 1–365 (the UI uses 7, 30, 90). |
| `tz` | server `TIME_ZONE` | IANA zone (e.g. `Asia/Kolkata`). Decides which calendar day a lead belongs to. The UI sends the browser's zone. |

Population: leads that are not deleted and not converted (identical to the leads list).

Response `200`:

```json
{
  "range_days": 30,
  "generated_at": "2026-10-16T06:30:00+00:00",
  "leads": {
    "total": 6,
    "new_in_range": 6,
    "new_previous_range": 0,
    "converted": 1,
    "by_status": [{ "status": "Contacted", "count": 1 }],
    "by_source": [{ "source": "Cold Call", "count": 2 }],
    "created_per_day": [{ "date": "2026-09-17", "count": 0 }]
  },
  "is_sampled": false,
  "is_partial": false
}
```

- `total`, `by_status`: all open leads of the company (the pipeline).
- `new_in_range`, `by_source`, `created_per_day`: leads created in the last `range` calendar days, today included.
- `new_previous_range`: the same-length window immediately before it.
- `created_per_day` always contains every day of the window (empty days are `0`).
- `converted`: converted, non-deleted leads.
- `400` for a bad `range` or unknown `tz`; `401/403` as for the leads list.

Cost: 4 aggregate queries, no row transfer. Backed by the index
`leads_dashboard_idx (company, is_deleted, is_converted, created_at)` — run
`python manage.py migrate` (migration `leads/0007_leads_dashboard_idx`).

## Possible next endpoints (not implemented)

- `GET /api/meetings/upcoming/?days=7` — the dashboard currently fetches the latest 50 meetings and filters client-side, which can miss meetings once more than 50 exist in the future.
- `GET /api/tasks/my-summary/` — overdue / today / upcoming counts plus the first rows, so the dashboard doesn't need to page and group tasks in the browser.
- `GET /api/dashboard/summary/?range=30` — stats + my tasks + schedule + recent leads in one response (one round trip instead of four) if the page still feels slow on high-latency links.
