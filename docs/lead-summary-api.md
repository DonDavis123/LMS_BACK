# Lead summary (Google Gemini)

Why: someone picking up a lead should understand it in five seconds. A user
clicks **Generate summary** on the lead page and the backend writes a short
briefing from the lead's whole history.

Same rules as the other lead endpoints: JWT, company user
(`IsAuthenticated` + `IsCompanyUser`), tenant scoped. A lead of another company
behaves like one that does not exist (`404`).

Nothing is generated when a lead is opened and **nothing is stored**: every
click is one model request and the result lives only in the response.

## Endpoint

`POST /api/leads/<lead_id>/summary/` (no body)

```json
{
  "lead_id": "…",
  "headline": "Asha Nair (Acme) is a hot retail lead, last contacted on 12 Nov and waiting for a revised quote.",
  "key_points": ["Asked for a quote on 5 Nov", "Call on 12 Nov: interested, wants a discount"],
  "next_steps": ["Send the revised quote by Friday"],
  "generated_at": "2026-11-17T12:00:00Z",
  "model_name": "gemini-2.5-flash",
  "timeline_events_used": 14,
  "calls_used": 3
}
```

| Status | Meaning |
|---|---|
| `200` | Summary written. |
| `404` | Lead not found (or not in your company). |
| `502` | The model failed; `detail` is safe to show. |
| `503` | No `GEMINI_API_KEY` is set on the server. |

## What the summary is based on

* the lead's own fields and owner,
* its timeline, latest 40 events (status changes, edits, tasks, meetings,
  calls, emails),
* its latest 10 calls, with the summary and action items of up to 5 transcribed
  recordings (see `call-transcription-api.md`).

All free text is cut to a fixed length and sent to the model as data between
markers; the system instruction tells it to ignore instructions inside it,
because lead data can come from the public lead-capture form.

## Settings (all optional)

The Gemini key and model are the ones call transcription already uses
(`GEMINI_API_KEY`, `GEMINI_MODEL`).

| Setting | Default |
|---|---|
| `LEAD_SUMMARY_LANGUAGE` | `CALL_TRANSCRIPTION_SUMMARY_LANGUAGE`, else `English` |
| `LEAD_SUMMARY_TIMEOUT_SECONDS` | `60` |

They are read with `getattr`, so no `settings.py` change is needed.
