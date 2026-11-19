# Contact summary (Google Gemini)

Why: someone picking up a contact should understand the relationship in five
seconds. A user clicks **Generate summary** on the contact page and the backend
writes a short briefing from the contact's whole history.

Same behaviour as the lead summary (`lead-summary-api.md`), for contacts. Same
rules as the other contact endpoints: JWT, company user
(`IsAuthenticated` + `IsCompanyUser`), tenant scoped. A contact of another
company, or a deleted contact, behaves like one that does not exist (`404`).

Nothing is generated when a contact is opened: every **Generate** / **Refresh**
click is one model request. The result is **stored** (table
`contact_summaries`, one row per contact), so the contact page shows the last
summary the next time it is opened without calling the model. A refresh
**permanently deletes** the old summary and stores the new one in its place
(delete + insert in one transaction; no history, no soft delete). If the model
fails, the old summary is left untouched.

## Endpoints

### `GET /api/contacts/<contact_id>/summary/`

Returns the stored summary. Never calls the model, so it is free to call
whenever a contact page opens. Same JSON as the `POST` below, with
`generated_at` = when it was written.

| Status | Meaning |
|---|---|
| `200` | The stored summary. |
| `204` | No summary has been generated for this contact yet (empty body). |
| `404` | Contact not found (or not in your company). |

### `POST /api/contacts/<contact_id>/summary/` (no body)

Writes a fresh summary, stores it in place of the old one and returns it.

```json
{
  "contact_id": "…",
  "headline": "Asha Nair is the buyer at Acme, last spoke on 12 Nov and is waiting for a revised quote.",
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
| `200` | Summary written and stored (the previous one is gone). |
| `404` | Contact not found (or not in your company). |
| `502` | The model failed; `detail` is safe to show. |
| `503` | No `GEMINI_API_KEY` is set on the server. |

## What the summary is based on

* the contact's own fields, its account and its owner,
* its timeline, latest 40 events (edits, tasks, meetings, calls, emails),
* its latest 10 calls, with the summary and action items of up to 5 transcribed
  recordings (see `call-transcription-api.md`).

All free text is cut to a fixed length and sent to the model as data between
markers; the system instruction tells it to ignore instructions inside it.

## Settings (all optional)

The Gemini key and model are the ones call transcription already uses
(`GEMINI_API_KEY`, `GEMINI_MODEL`).

| Setting | Default |
|---|---|
| `CONTACT_SUMMARY_LANGUAGE` | `CALL_TRANSCRIPTION_SUMMARY_LANGUAGE`, else `English` |
| `CONTACT_SUMMARY_TIMEOUT_SECONDS` | `60` |

They are read with `getattr`, so no `settings.py` change is needed.
