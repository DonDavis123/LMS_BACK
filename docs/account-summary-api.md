# Account summary (Google Gemini)

Why: someone picking up an account should understand the relationship in five
seconds. A user clicks **Generate summary** on the account page and the backend
writes a short briefing from the account's whole history.

Same behaviour as the lead summary (`lead-summary-api.md`), for accounts. Same
rules as the other account endpoints: JWT, company user
(`IsAuthenticated` + `IsCompanyUser`), tenant scoped. An account of another
company, or a deleted account, behaves like one that does not exist (`404`).

Nothing is generated when an account is opened: every **Generate** / **Refresh**
click is one model request. The result is **stored** (table
`account_summaries`, one row per account), so the account page shows the last
summary the next time it is opened without calling the model. A refresh
**permanently deletes** the old summary and stores the new one in its place
(delete + insert in one transaction; no history, no soft delete). If the model
fails, the old summary is left untouched.

## Endpoints

### `GET /api/accounts/<account_id>/summary/`

Returns the stored summary. Never calls the model, so it is free to call
whenever an account page opens. Same JSON as the `POST` below, with
`generated_at` = when it was written.

| Status | Meaning |
|---|---|
| `200` | The stored summary. |
| `204` | No summary has been generated for this account yet (empty body). |
| `404` | Account not found (or not in your company). |

### `POST /api/accounts/<account_id>/summary/` (no body)

Writes a fresh summary, stores it in place of the old one and returns it.

```json
{
  "account_id": "…",
  "headline": "Acme Retail is a 250-person retail customer with 3 active contacts; the last call on 12 Nov was about a revised quote.",
  "key_points": ["Asha Nair asked for a quote on 5 Nov", "Call on 12 Nov: interested, wants a discount"],
  "next_steps": ["Send the revised quote by Friday"],
  "generated_at": "2026-11-17T12:00:00Z",
  "model_name": "gemini-2.5-flash",
  "timeline_events_used": 14,
  "calls_used": 3,
  "contacts_used": 3
}
```

| Status | Meaning |
|---|---|
| `200` | Summary written and stored (the previous one is gone). |
| `404` | Account not found (or not in your company). |
| `502` | The model failed; `detail` is safe to show. |
| `503` | No `GEMINI_API_KEY` is set on the server. |

## What the summary is based on

* the account's own fields and owner,
* its contacts (up to 10: name, title, email, phone, owner),
* its timeline, latest 40 events. Deals, tasks and calls of the account's
  contacts write to the account timeline too, so they are covered here,
* its latest 10 calls (calls logged with the account, which always belong to
  one of its contacts), with the summary and action items of up to 5
  transcribed recordings (see `call-transcription-api.md`).

All free text is cut to a fixed length and sent to the model as data between
markers; the system instruction tells it to ignore instructions inside it.

## Settings (all optional)

The Gemini key and model are the ones call transcription already uses
(`GEMINI_API_KEY`, `GEMINI_MODEL`).

| Setting | Default |
|---|---|
| `ACCOUNT_SUMMARY_LANGUAGE` | `CALL_TRANSCRIPTION_SUMMARY_LANGUAGE`, else `English` |
| `ACCOUNT_SUMMARY_TIMEOUT_SECONDS` | `60` |

They are read with `getattr`, so no `settings.py` change is needed.
