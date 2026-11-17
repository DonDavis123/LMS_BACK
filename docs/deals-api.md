# Deals API

Deals track a sales opportunity from first quote to won / lost. This part covers
the core module: create, read, update, delete and "move to stage". (Board,
forecast and lead conversion are added in Part 2.)

All endpoints are under `/api/deals/`.

Auth: JWT, company user (`IsAuthenticated` + `IsCompanyUser`). Every query is
scoped to the caller's company: another company's deal behaves exactly like a
missing one. Platform superadmins get `403`, anonymous callers `401`.

Errors are always `{"detail": "..."}` with `400` (validation / business rule),
`404` (detail GET only) or `401/403`. Money is a decimal and is returned as a
string, e.g. `"100000.00"`.

## Stages

Fixed for v1. The default probabilities live in one place
(`DEFAULT_PROBABILITY` in `src/modules/deals/domain/enums/deal_stage.py`).

| Stage | Default probability | Closed? |
|---|---|---|
| `New` | 10 | no |
| `Quotation Sent` | 40 | no |
| `Negotiation` | 70 | no |
| `Won` | 100 | yes |
| `Lost` | 0 | yes |

### Stage rules

Applied by `Deal.move_to_stage()`, so they are identical for
`POST /{id}/move/`, `PATCH /{id}/` with a `stage`, and `POST /` with a `stage`.

- Moving to an **open** stage sets `probability` to that stage's default,
  unless the caller sent an explicit `probability`. A deal that is already in
  that stage and gets no explicit value keeps its current probability.
- **Won** forces `probability = 100`, sets `closed_at` to now and clears
  `lost_reason`. A `probability` sent with it is ignored.
- **Lost** forces `probability = 0`, **requires** a non-blank `lost_reason`
  (max 255 characters, surrounding spaces are trimmed) and sets `closed_at`.
  A deal that is already Lost keeps its stored reason if none is sent.
- Moving a closed deal back to an open stage clears `closed_at` and
  `lost_reason`.
- Moving a closed deal to the same closed stage keeps its `closed_at`;
  Won → Lost (or Lost → Won) sets a new `closed_at`.
- `probability` must be an integer from 0 to 100 (`true`, `12.5`, `"abc"` are
  rejected). A failed move changes nothing and records no timeline event.
- A closed deal's probability is fixed: `PATCH {"probability": 50}` on a Won
  deal is rejected (sending the same fixed value is fine).
- `lost_reason` can only be patched on a deal that is Lost.

## Fields

| Field | Notes |
|---|---|
| `id` | UUID |
| `name` | required, non-blank, max 255 |
| `amount` | decimal, `>= 0`, max 2 decimals, default `0` |
| `expected_close_date` | date, nullable. Past dates are allowed |
| `stage` | one of the stages above, default `New` |
| `probability` | integer 0–100, defaults from the stage |
| `owner_id` / `owner_name` | required; same company, active, role `ADMIN` or `SUPERADMIN` |
| `account_id` / `account_name` | optional, same company, not deleted |
| `contact_id` / `contact_name` | optional, same company, not deleted |
| `source_lead_id` / `source_lead_name` | the lead it came from (set on create only) |
| `lead_source` | copied from the source lead when it exists (an explicit value wins) |
| `description` | text, nullable |
| `lost_reason` | required when the stage is Lost, otherwise `null` |
| `closed_at` | set on Won / Lost, cleared on reopen |
| `created_by_id`, `created_at`, `updated_at` | read only |

Rules: at least one of `account_id` / `contact_id` is required. If both are
given and the contact belongs to a different account the request is rejected
(`"Selected contact does not belong to the selected account."`). A contact
without an account can be combined with any account.

## Endpoints

### `GET /api/deals/`

Paginated list of the company's non-deleted deals, newest first by default.

Query params (same conventions as tasks): `page` (default 1), `page_size`
(default 20, max 50), `search` (case-insensitive match on the deal name),
`sort_by`, `sort_direction` (`asc` / `desc`), `filters` (JSON array of
`{"field", "operator", "value"}`).

| Filter field | Operators | Value |
|---|---|---|
| `stage` | `equals`, `not_equals`, `in`, `not_in` | stage name / list of names |
| `owner`, `account`, `contact` | `equals`, `not_equals`, `in`, `not_in` | UUID / list of UUIDs |
| `expected_close_date` | `equals`, `before`, `after`, `between` | `YYYY-MM-DD`, or `{"from", "to"}` (inclusive) |
| `amount`, `probability` | `equals`, `greater_than`, `less_than`, `between` | number, or `{"from", "to"}` (inclusive) |
| `name` | `contains`, `equals`, `starts_with`, `ends_with`, `not_contains`, `not_equals` | string |

Sortable: `name`, `amount`, `expected_close_date`, `stage`, `probability`,
`created_at`, `owner`. Text sorts are case-insensitive, empty values come last,
and `-created_at, -id` breaks ties so pages are stable. An unsupported sort or
filter, a bad operator or a bad value is `400`.

```json
{
  "results": [
    {
      "id": "6f1c…",
      "name": "Big Deal",
      "amount": "100000.00",
      "expected_close_date": "2026-12-31",
      "stage": "Negotiation",
      "probability": 70,
      "owner_id": "…", "owner_name": "Admin A",
      "account_id": "…", "account_name": "Acme Corp",
      "contact_id": null, "contact_name": null,
      "source_lead_id": null, "source_lead_name": null,
      "lead_source": null,
      "description": null,
      "lost_reason": null,
      "closed_at": null,
      "created_by_id": "…",
      "created_at": "2026-11-18T09:00:00+05:30",
      "updated_at": "2026-11-18T09:00:00+05:30"
    }
  ],
  "pagination": { "page": 1, "page_size": 20, "total": 1, "total_pages": 1 }
}
```

### `POST /api/deals/`

Body: `name`, `owner_id` and one of `account_id` / `contact_id` are required;
`amount`, `expected_close_date`, `stage`, `probability`, `source_lead_id`,
`lead_source`, `description`, `lost_reason` are optional. Records
`DEAL_CREATED`. Returns `201` with the deal (base fields, no `*_name`).

### `GET /api/deals/{id}/`

The deal with owner, account, contact and source lead names (same shape as a
list row). `404 {"detail": "Deal not found."}` when it does not exist, is
deleted or belongs to another company.

### `PATCH /api/deals/{id}/`

Partial update of `name`, `amount`, `expected_close_date`, `stage`,
`probability`, `owner_id`, `account_id`, `contact_id`, `description`,
`lost_reason`. A stage change follows the stage rules above. Records
`DEAL_UPDATED` (with the field changes) when something changed, and the stage
events below when the stage changed. Returns `200` with the deal (base fields).

### `DELETE /api/deals/{id}/`

Soft delete. Records `DEAL_DELETED`. `200 {"message": "Deal deleted successfully."}`.
Like tasks, an unknown / foreign / already deleted deal answers
`400 {"detail": "Deal not found."}` for PATCH, DELETE and move.

### `POST /api/deals/{id}/move/`

Body: `{"stage": "...", "probability"?: n, "lost_reason"?: "..."}`. Applies the
stage rules and returns `200` with the updated deal (base fields). Records
`DEAL_STAGE_CHANGED` (`metadata.from_stage`, `metadata.to_stage`) and also
`DEAL_WON` or `DEAL_LOST` when the deal closes.

## Timeline

`DEAL` is a timeline entity type; `GET /api/timeline/deals/{id}/` returns a
deal's history. Each event targets `("DEAL", id)` plus `("CONTACT", id)` and
`("ACCOUNT", id)` when set, so deals also show up on the contact and account
timelines.

| Event type | When |
|---|---|
| `DEAL_CREATED` | deal created (also `DEAL_WON` / `DEAL_LOST` if it is created closed) |
| `DEAL_UPDATED` | PATCH (or a same-stage move) changed something |
| `DEAL_STAGE_CHANGED` | the stage changed (move or PATCH) |
| `DEAL_WON` | the deal moved to Won |
| `DEAL_LOST` | the deal moved to Lost (`metadata.lost_reason`) |
| `DEAL_DELETED` | soft delete |

## Setup

```
python manage.py migrate        # deals/0001_initial
```

Table `deals` has indexes `(company, is_deleted, stage)` and
`(company, is_deleted, expected_close_date)`.
