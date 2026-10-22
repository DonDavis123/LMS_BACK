# Calls API

Why: a call log is the history of conversations with a lead or a contact. The
lead page and the contact page both need that history, and clicking a call must
show everything that happened to it (who logged it, every edit with old and new
values, and the other calls on the same record).

All endpoints are tenant scoped: a company only ever sees, changes or logs calls
against its own leads, contacts and accounts. Records of another company behave
exactly like records that do not exist.

Auth: JWT, company user (`IsAuthenticated` + `IsCompanyUser`), same as tasks.
Unauthenticated requests get `401`/`403`.

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/calls/` | Paginated, filterable list (no history in the rows). |
| `POST` | `/api/calls/` | Log a call from a lead or from a contact. |
| `GET` | `/api/calls/records/` | **One row per lead / contact** (latest call, call count, latest update). Powers the Calls table. |
| `GET` | `/api/calls/<call_id>/` | Call detail with `change_history` and `related_calls`. |
| `GET` | `/api/calls/<call_id>/history/` | Detailed history of **every call** on the same lead / contact (date and time, duration, notes, edits). |
| `PATCH` | `/api/calls/<call_id>/` | Edit start time, duration, type, outcome or description. |
| `DELETE` | `/api/calls/<call_id>/` | Soft delete. |
| `GET` | `/api/timeline/calls/<call_id>/` | Raw timeline events of one call (`CALL` entity type). |

The call also shows up in `/api/timeline/leads/<id>/`, `/api/timeline/contacts/<id>/`
and, when it has an account, `/api/timeline/accounts/<id>/`.

## Enum values

| Field | Values |
|---|---|
| `call_type` | `Outbound` (default), `Inbound` |
| `outcome` | `Connected`, `Not Attended`, `Busy`, `Voicemail`, `Wrong Number`, `Callback Requested` |
| `entry_method` | `MANUAL` (default), `TIMER` |
| timeline `event_type` | `CALL_LOGGED`, `CALL_UPDATED`, `CALL_DELETED` |

`duration_seconds` is always seconds: a manual entry of 12 minutes is sent as
`720`, a timer entry sends the measured seconds.

## `POST /api/calls/`

A call belongs to **exactly one** of a lead or a contact. An `account_id` is only
allowed together with a `contact_id`.

| Field | Type | Rules |
|---|---|---|
| `lead_id` | UUID, nullable | Lead of the company, not deleted. |
| `contact_id` | UUID, nullable | Contact of the company, not deleted. |
| `account_id` | UUID, nullable | Account of the company, not deleted. Requires `contact_id`. |
| `owner_id` | UUID, optional | The user who made the call. Defaults to the request user. Must be an active ADMIN or SUPERADMIN of the company. |
| `call_type` | choice, optional | Default `Outbound`. |
| `outcome` | choice, **required** | |
| `call_start_time` | datetime, **required** | At most 5 minutes in the future. |
| `duration_seconds` | integer, optional | `0`–`86400`, default `0`. |
| `description` | string, optional | Blank allowed, max 1000 characters. |
| `entry_method` | choice, optional | Default `MANUAL`. |

Log a call from a lead:

```json
{
  "lead_id": "6d1f0c3e-0f4c-4a52-9a67-3c2f3b0c9a11",
  "outcome": "Connected",
  "call_start_time": "2026-10-21T10:30:00+05:30",
  "duration_seconds": 250,
  "description": "Discussed pricing and next steps."
}
```

Log a call from a contact (the account is optional):

```json
{
  "contact_id": "0b9a3f52-7a52-4f0e-8ad3-5e4c1c1c7d02",
  "account_id": "a3a5c1de-2d6b-41ab-93c6-0f7d2d7a1b33",
  "outcome": "Callback Requested",
  "call_type": "Inbound",
  "call_start_time": "2026-10-21T11:00:00+05:30",
  "duration_seconds": 95,
  "entry_method": "TIMER"
}
```

Response `201`:

```json
{
  "id": "f4c7d1a0-3b52-4a68-8f0e-2f6a9c1d7e44",
  "lead_id": "6d1f0c3e-0f4c-4a52-9a67-3c2f3b0c9a11",
  "contact_id": null,
  "account_id": null,
  "owner_id": "2f9b6a64-5a3e-4d27-b0a1-9c6f7e2d1a55",
  "call_type": "Outbound",
  "outcome": "Connected",
  "call_start_time": "2026-10-21T10:30:00+05:30",
  "duration_seconds": 250,
  "duration_label": "4 min 10 sec",
  "description": "Discussed pricing and next steps.",
  "entry_method": "MANUAL",
  "created_by_id": "2f9b6a64-5a3e-4d27-b0a1-9c6f7e2d1a55",
  "created_at": "2026-10-21T10:36:12.482911+05:30",
  "updated_at": "2026-10-21T10:36:12.482911+05:30"
}
```

Logging a call never changes earlier calls; it only adds a row and a
`CALL_LOGGED` timeline event.

## `GET /api/calls/`

Same query parameters and response shape as `GET /api/tasks/`: `page` (default
`1`), `page_size` (default `20`, max `50`), `sort_by`, `sort_direction`
(`asc`/`desc`), `search` (free text, max 100 characters) and `filters` (a JSON
array of `{field, operator, value}`).

`search` is a case-insensitive partial match on the lead / contact name, the
account name, the owner's name and the call notes. It combines (AND) with
`filters`.

Without `sort_by` the list is newest call first (`call_start_time` descending).

| Filter field | Operators | Value |
|---|---|---|
| `lead_id`, `contact_id`, `account_id`, `owner`, `created_by` | `equals`, `not_equals`, `in`, `not_in` | UUID (list of UUIDs for `in`/`not_in`) |
| `call_type`, `outcome` | `equals`, `not_equals`, `in`, `not_in` | enum value (list for `in`/`not_in`) |
| `call_start_time`, `created_at` | `equals`, `before`, `after`, `between` | ISO date or datetime (`{"from": ..., "to": ...}` for `between`). A date-only value (`2030-01-15`) is the whole calendar day in the project time zone, and `before` / `between` include the last day. A full datetime is an exact instant. |
| `duration_seconds` | `equals`, `not_equals`, `in`, `not_in`, `after` (at least), `before` (at most) | number of seconds (list for `in`/`not_in`) |
| `record_type` | `equals`, `not_equals`, `in`, `not_in` | `LEAD` or `CONTACT` (list for `in`/`not_in`) |
| `record_name` (lead's or contact's name), `account_name`, `description` | `contains`, `not_contains`, `equals`, `not_equals`, `starts_with`, `ends_with` | text |

Sortable columns: `call_start_time`, `duration_seconds`, `outcome`, `call_type`,
`created_at`, `record_name` (the lead's or contact's name), `owner` (owner's
name) and `description`. Text columns sort case-insensitively.

### Lead page history

```
GET /api/calls/?filters=[{"field":"lead_id","operator":"equals","value":"<lead uuid>"}]&sort_by=call_start_time&sort_direction=desc&page_size=50
```

### Contact page history

```
GET /api/calls/?filters=[{"field":"contact_id","operator":"equals","value":"<contact uuid>"}]&sort_by=call_start_time&sort_direction=desc&page_size=50
```

(URL-encode the `filters` value when building the URL in code.)

Response `200`:

```json
{
  "results": [
    {
      "id": "f4c7d1a0-3b52-4a68-8f0e-2f6a9c1d7e44",
      "lead_id": "6d1f0c3e-0f4c-4a52-9a67-3c2f3b0c9a11",
      "lead_name": "Priya Nair",
      "contact_id": null,
      "contact_name": null,
      "account_id": null,
      "account_name": null,
      "owner_id": "2f9b6a64-5a3e-4d27-b0a1-9c6f7e2d1a55",
      "owner_name": "Asha Verma",
      "call_type": "Outbound",
      "outcome": "Connected",
      "call_start_time": "2026-10-21T10:30:00+05:30",
      "duration_seconds": 250,
      "duration_label": "4 min 10 sec",
      "description": "Discussed pricing and next steps.",
      "entry_method": "MANUAL",
      "created_by_id": "2f9b6a64-5a3e-4d27-b0a1-9c6f7e2d1a55",
      "created_at": "2026-10-21T10:36:12.482911+05:30",
      "updated_at": "2026-10-21T10:36:12.482911+05:30"
    }
  ],
  "pagination": { "page": 1, "page_size": 50, "total": 1, "total_pages": 1 }
}
```

List rows never include history; use the detail endpoint for that.

## `GET /api/calls/records/`

The Calls table lists every lead / contact **once**, however many calls were
logged on it. Same query parameters as `GET /api/calls/` (`page`, `page_size`,
`sort_by`, `sort_direction`, `search`, `filters`) and the same filter fields.
Search and filters apply to the calls first, so a record is listed when at least
one of its calls matches, and `call_count` / `latest_call` are computed over the
matching calls (searching a note keyword can therefore show a count lower than
the record's total).

Without `sort_by` the list is the most recently logged-or-edited record first
(`last_updated_at` descending).

Sortable columns: `call_start_time`, `duration_seconds`, `outcome`, `call_type`,
`created_at`, `record_name`, `owner`, `description` (all of the record's latest
call), plus `call_count` and `last_updated_at`.

Response `200`:

```json
{
  "results": [
    {
      "record_type": "LEAD",
      "record_id": "6d1f0c3e-0f4c-4a52-9a67-3c2f3b0c9a11",
      "record_name": "Priya Nair",
      "call_count": 3,
      "last_updated_at": "2026-10-21T12:02:40.118204+05:30",
      "latest_call": {
        "id": "f4c7d1a0-3b52-4a68-8f0e-2f6a9c1d7e44",
        "lead_id": "6d1f0c3e-0f4c-4a52-9a67-3c2f3b0c9a11",
        "lead_name": "Priya Nair",
        "contact_id": null,
        "contact_name": null,
        "account_id": null,
        "account_name": null,
        "owner_id": "2f9b6a64-5a3e-4d27-b0a1-9c6f7e2d1a55",
        "owner_name": "Asha Verma",
        "call_type": "Outbound",
        "outcome": "Connected",
        "call_start_time": "2026-10-21T10:30:00+05:30",
        "duration_seconds": 300,
        "duration_label": "5 min 0 sec",
        "description": "Customer asked for a revised quote.",
        "entry_method": "MANUAL",
        "created_by_id": "2f9b6a64-5a3e-4d27-b0a1-9c6f7e2d1a55",
        "created_at": "2026-10-21T10:36:12.482911+05:30",
        "updated_at": "2026-10-21T12:02:40.118204+05:30"
      },
      "latest_update": {
        "id": "9c2d51a8-6f0b-4b79-8a41-1d3e5f7a9b01",
        "event_type": "CALL_UPDATED",
        "actor": { "id": "2f9b6a64-5a3e-4d27-b0a1-9c6f7e2d1a55", "name": "Asha Verma" },
        "message": "Call was updated. Changes: Duration (seconds): 250 → 300",
        "call_id": "f4c7d1a0-3b52-4a68-8f0e-2f6a9c1d7e44",
        "changes": { "duration_seconds": { "old_value": 250, "new_value": 300 } },
        "created_at": "2026-10-21T12:02:40.131552+05:30"
      }
    }
  ],
  "pagination": { "page": 1, "page_size": 10, "total": 1, "total_pages": 1 }
}
```

- `latest_call` has exactly the fields of a `GET /api/calls/` row; open
  `/api/calls/<latest_call.id>/` for its detail.
- `latest_update` is the newest call event on the record (`CALL_LOGGED`,
  `CALL_UPDATED` or `CALL_DELETED`); `changes` is `{}` unless it is a
  `CALL_UPDATED`. It is `null` for calls that have no timeline event.
- `GET /api/calls/` is unchanged and still returns one row per call (used by the
  per-lead / per-contact call panels).

## `GET /api/calls/<call_id>/history/`

Detailed history of the lead / contact the call belongs to: every call that was
logged, edited or deleted on it, newest first. Each event carries a `call`
snapshot — the call **as it was at that moment** (rebuilt by undoing later edits,
so it is exact for older calls too). `duration_seconds` is `0` when no duration
was entered and `description` is `null` when there are no notes; clients show
them only when present. `call.*` fields can be `null` for a deleted call whose
original values were never recorded.

Response `200`:

```json
{
  "related_record": { "type": "LEAD", "id": "6d1f0c3e-0f4c-4a52-9a67-3c2f3b0c9a11", "name": "Priya Nair" },
  "total_calls_for_record": 2,
  "events": [
    {
      "id": "9c2d51a8-6f0b-4b79-8a41-1d3e5f7a9b01",
      "event_type": "CALL_UPDATED",
      "call_id": "f4c7d1a0-3b52-4a68-8f0e-2f6a9c1d7e44",
      "actor": { "id": "2f9b6a64-5a3e-4d27-b0a1-9c6f7e2d1a55", "name": "Asha Verma" },
      "message": "Call was updated. Changes: Duration (seconds): 250 → 300",
      "changes": { "duration_seconds": { "old_value": 250, "new_value": 300 } },
      "created_at": "2026-10-21T12:02:40.131552+05:30",
      "call": {
        "call_start_time": "2026-10-21T10:30:00+05:30",
        "call_type": "Outbound",
        "outcome": "Connected",
        "duration_seconds": 300,
        "duration_label": "5 min 0 sec",
        "description": "Customer asked for a revised quote.",
        "owner_name": "Asha Verma"
      }
    }
  ]
}
```

A call of another company, a deleted call or an unknown id returns `404`
`{"detail": "Call not found."}`.

## `GET /api/calls/<call_id>/`

Every list-row field plus:

- `related_record`: the lead or contact the call was made on.
- `change_history`: the call's timeline, **newest first**. `changes` is
  `field -> {old_value, new_value}` for `CALL_UPDATED` and `{}` for `CALL_LOGGED`.
- `related_calls`: the *other* calls on the same lead/contact, newest first, at most 50.
- `total_calls_for_record`: every active call on that lead/contact, including this one.

Response `200` (a call that was logged and then edited once):

```json
{
  "id": "f4c7d1a0-3b52-4a68-8f0e-2f6a9c1d7e44",
  "lead_id": "6d1f0c3e-0f4c-4a52-9a67-3c2f3b0c9a11",
  "lead_name": "Priya Nair",
  "contact_id": null,
  "contact_name": null,
  "account_id": null,
  "account_name": null,
  "owner_id": "2f9b6a64-5a3e-4d27-b0a1-9c6f7e2d1a55",
  "owner_name": "Asha Verma",
  "call_type": "Outbound",
  "outcome": "Connected",
  "call_start_time": "2026-10-21T10:30:00+05:30",
  "duration_seconds": 300,
  "duration_label": "5 min 0 sec",
  "description": "Customer asked for a revised quote.",
  "entry_method": "MANUAL",
  "created_by_id": "2f9b6a64-5a3e-4d27-b0a1-9c6f7e2d1a55",
  "created_at": "2026-10-21T10:36:12.482911+05:30",
  "updated_at": "2026-10-21T12:02:40.118204+05:30",
  "is_latest": true,
  "related_record": {
    "type": "LEAD",
    "id": "6d1f0c3e-0f4c-4a52-9a67-3c2f3b0c9a11",
    "name": "Priya Nair"
  },
  "change_history": [
    {
      "id": "9c2d51a8-6f0b-4b79-8a41-1d3e5f7a9b01",
      "event_type": "CALL_UPDATED",
      "actor": { "id": "2f9b6a64-5a3e-4d27-b0a1-9c6f7e2d1a55", "name": "Asha Verma" },
      "message": "Call was updated. Changes: Duration (seconds): 250 → 300; Description: Discussed pricing and next steps. → Customer asked for a revised quote.",
      "changes": {
        "description": {
          "old_value": "Discussed pricing and next steps.",
          "new_value": "Customer asked for a revised quote."
        },
        "duration_seconds": { "old_value": 250, "new_value": 300 }
      },
      "created_at": "2026-10-21T12:02:40.131552+05:30"
    },
    {
      "id": "4b7e9d20-1a3c-4f58-9e62-7c8d0a1b2c03",
      "event_type": "CALL_LOGGED",
      "actor": { "id": "2f9b6a64-5a3e-4d27-b0a1-9c6f7e2d1a55", "name": "Asha Verma" },
      "message": "Call logged (Connected, 4 min 10 sec).",
      "changes": {},
      "created_at": "2026-10-21T10:36:12.497320+05:30"
    }
  ],
  "related_calls": [
    {
      "id": "e1a2b3c4-d5e6-4f70-8a91-b2c3d4e5f607",
      "call_start_time": "2026-10-20T16:10:00+05:30",
      "duration_seconds": 60,
      "duration_label": "1 min 0 sec",
      "outcome": "Voicemail",
      "call_type": "Outbound",
      "description": null,
      "owner_name": "Asha Verma"
    }
  ],
  "total_calls_for_record": 2
}
```

A call of another company, a deleted call, or an unknown id returns `404`
`{"detail": "Call not found."}`.

## `PATCH /api/calls/<call_id>/`

Editable fields (all optional): `call_start_time`, `duration_seconds`,
`call_type`, `outcome`, `description`. They follow the same rules as on create.

`lead_id`, `contact_id`, `account_id`, `owner_id`, `entry_method` and any other
field are immutable and rejected with `400`:

```json
{ "lead_id": ["This field cannot be updated."] }
```

Only fields whose value actually changed are written to the timeline: a
`CALL_UPDATED` event with `metadata.changes`. A PATCH that changes nothing
(empty body, same values, same instant in another UTC offset) returns `200`
and writes no event.

**Only the latest call can be updated.** A call is the latest when it has the
newest `call_start_time` (ties broken by id) among the active calls of its lead
/ contact. Once a newer call exists, the older one is read-only history and
`PATCH` returns `400` `{"detail": "Only the latest call can be updated. Earlier calls are kept as read-only history."}`.
`GET /api/calls/<call_id>/` exposes this as `is_latest`.

Response `200`: the same shape as the `POST` response.

## `DELETE /api/calls/<call_id>/`

Soft delete; writes a `CALL_DELETED` event on the call's lead/contact (and account)
timeline.

```json
{ "message": "Call deleted successfully." }
```

A deleted call disappears from the list and the detail endpoint (`404`), is no
longer counted in `related_calls` / `total_calls_for_record`, and
`/api/timeline/calls/<call_id>/` returns `404`.

## Delete cascade

| When this is deleted | What happens to its calls |
|---|---|
| Lead (`DELETE /api/leads/<id>/delete/`) | All its calls are soft deleted, and the timeline events of every one of those calls are removed. |
| Contact (`DELETE /api/contacts/<id>/delete/`) | Same. |
| Account (`DELETE /api/accounts/<id>/delete/`) | Handled like tasks: a call that carries the account always belongs to a contact, so it **stays** a contact call and only its `account_id` is cleared. Any legacy account-only call would be soft deleted together with its timeline events. |
| User (retire) | Calls **owned** by the user are permanently deleted, like their tasks. `GET /api/users/<id>/deletion-preview/` reports the number as `impact.calls` and `permanent_deletions.calls` (new, additive fields). |
| Lead converted | Nothing. A converted lead is only flagged `is_converted`, so its calls stay visible ("View Lead History"). Calls are not moved to the new contact. |

Everything runs in the same database transaction as the delete itself: if any
step fails, nothing (lead, calls, timeline) is changed. Calls of other
leads/contacts/companies are never touched.

Note: the timeline of a call logged on a contact **with an account** is shared
with that account. When the contact is deleted the call's own timeline and the
contact's timeline are cleared, but the event keeps its account target, as it does
for tasks.

## Errors

| Status | When | Body |
|---|---|---|
| `400` | Field validation (wrong type/choice, duration outside `0`–`86400`, description over 1000 characters, unknown or immutable field on `PATCH`) | DRF field errors, e.g. `{"duration_seconds": ["Ensure this value is less than or equal to 86400."]}` |
| `400` | Business rules: updating a call that is no longer the latest on its lead / contact, neither lead nor contact, both, account without contact, start time more than 5 minutes in the future, deleted/unknown lead, contact or account, invalid owner, bad `filters`/`sort_by` | `{"detail": "..."}` |
| `401` / `403` | Not authenticated, no company, suspended company | |
| `404` | Unknown, deleted or foreign call on detail/`PATCH`/`DELETE`/call timeline | `{"detail": "Call not found."}` |

Examples of `detail` messages: `Call must be associated with exactly one of a lead or a contact.`,
`Call account requires an associated contact.`, `Call start time cannot be more than 5 minutes in the future.`,
`Selected lead not found.`, `Selected contact not found.`, `Call owner does not exist.`.
