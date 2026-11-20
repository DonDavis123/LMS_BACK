# Daily briefing (Google Gemini)

Why: a salesperson opens the dashboard and wants to know what to work on first.
The **Plan my day** button on the dashboard greeting card asks the backend to
sort the user's open tasks (with today's meetings in mind) and explain the order.

Same rules as the other company endpoints: JWT, company user
(`IsAuthenticated` + `IsCompanyUser`), tenant scoped. It only ever reads the
**caller's own** work, so it does not need the lead-view permission that
`/dashboard/stats/` needs.

Nothing is generated when the dashboard opens: every click is one model request,
and **nothing is stored** (no table, no migration).

## `POST /api/dashboard/briefing/`

Body (optional): `{ "tz": "Asia/Kolkata" }`. IANA zone that decides what "today"
is; defaults to the server `TIME_ZONE`. The UI sends the browser's zone.

```json
{
  "date": "2026-11-20",
  "generated_at": "2026-11-20T14:05:00+05:30",
  "model_name": "gemini-2.5-flash",
  "headline": "Busy afternoon: clear the overdue Acme quote, then finish the demo deck before 3 PM.",
  "counts": {
    "overdue_tasks": 1, "due_today_tasks": 2, "meetings_today": 1,
    "open_tasks_total": 4, "tasks_considered": 4
  },
  "priorities": [
    {
      "rank": 1, "task_id": "…", "subject": "Send revised quote to Acme",
      "priority": "High", "status": "Not Started", "due_date": "2026-11-17",
      "urgency": "overdue", "days_overdue": 3, "related_to": "Asha Nair",
      "bucket": "do_first", "reason": "Three days overdue and High priority."
    }
  ],
  "heads_up": ["Only one hour is free before your 3:00 PM meeting."]
}
```

`bucket` is `do_first`, `do_next` or `can_wait`; `urgency` is `overdue`, `today`,
`upcoming` or `no_due_date`. `priorities` is already sorted (`rank` 1 = first).

| Status | Meaning |
|---|---|
| `200` | Plan written. |
| `400` | Unknown `tz`. |
| `502` | The model failed; `detail` is safe to show. |
| `503` | No `GEMINI_API_KEY` is set on the server. |

## What the plan is based on

* open tasks (any status except Completed) whose **responsible** user is the
  caller (assignee, else owner: the same rule as the dashboard's My tasks),
  soonest due first, at most 50 (`open_tasks_total` is the real count);
* meetings the caller **hosts** that start today (caller's time zone) and have
  not ended yet. Meetings where the caller is only a participant are not included.

## What the model decides, and what it cannot

The model only chooses the order, the bucket and writes `reason`, `headline`
and `heads_up`. Everything else is the database's: subject, priority, status,
due date, urgency, counts. Server-side guards:

* a `ref` the model invents, or repeats, is dropped (it sees `T1`, `T2`…, never ids);
* an invalid bucket gets a default from urgency and priority;
* an **overdue or due-today task the model leaves out is added back** with a plain
  reason ("Overdue by 3 days."), so late work is never silently hidden;
* the plan is capped at 15 entries.

If there are no open tasks and no meetings left, the answer is returned
directly (`model_name: null`) without calling the model.

Task text can come from outside the company (lead names from the public
capture form), so it is cut to fixed lengths and sent as data between markers;
the system instruction tells the model to ignore instructions inside it.

## Settings (all optional)

Key and model are the ones the lead summary and call transcription use
(`GEMINI_API_KEY`, `GEMINI_MODEL`).

| Setting | Default |
|---|---|
| `DAILY_BRIEFING_LANGUAGE` | `CALL_TRANSCRIPTION_SUMMARY_LANGUAGE`, else `English` |
| `DAILY_BRIEFING_TIMEOUT_SECONDS` | `60` |

Read with `getattr`, so no `settings.py` change is needed. Like the lead summary,
the endpoint is not rate limited.
