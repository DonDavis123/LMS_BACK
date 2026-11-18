# Deals API

Deals track a sales opportunity from first quote to won / lost. This part covers
the core module (create, read, update, delete, "move to stage"), the Kanban
board, the forecast, and creating a deal while converting a lead.

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

## Board

### `GET /api/deals/board/`

Every stage as a column, in fixed order (`New`, `Quotation Sent`, `Negotiation`,
`Won`, `Lost`), so the Kanban screen needs one call. Empty stages are included.

| Query param | Default | Notes |
|---|---|---|
| `owner_id` | – | UUID. Only deals of that owner. |
| `expected_close_from`, `expected_close_to` | – | ISO dates, inclusive. Deals without an expected close date are left out when either is given. Apply to every column. |
| `search` | – | Case-insensitive match on the deal name. |
| `closed_within_days` | `30` | Integer 1–3650. Only for the `Won` and `Lost` columns: a closed deal shows when `closed_at` is within the last N days (rolling, `now - N days`). A closed deal without `closed_at` is never shown. Open columns are not affected. |

- `count`, `total_amount` and `weighted_amount` cover **all** matching deals of
  the column, even when `deals` is truncated.
- `deals` holds at most **50** cards per column: soonest `expected_close_date`
  first (no date last) for open stages, most recently closed first for `Won` /
  `Lost`. `has_more` is `true` when the column holds more than the cards sent.
- `weighted_amount` = sum of `amount * probability / 100` using each deal's own
  probability.
- Cost: one aggregated query for all counts and totals plus one query per
  column for the cards (`select_related`), independent of the number of deals.
- Invalid params: `400 {"detail": "..."}` (bad UUID or date, `closed_within_days`
  out of range, `expected_close_from` after `expected_close_to`).

```json
{
  "stages": [
    {
      "stage": "Quotation Sent",
      "default_probability": 40,
      "count": 1,
      "total_amount": "100000.00",
      "weighted_amount": "40000.00",
      "has_more": false,
      "deals": [
        {
          "id": "6f1c…", "name": "Website for Ravi's shop", "amount": "100000.00",
          "expected_close_date": "2026-11-30", "probability": 40,
          "owner_id": "…", "owner_name": "Dev",
          "account_id": "…", "account_name": "Ravi's shop",
          "contact_id": "…", "contact_name": "Ravi"
        }
      ]
    }
  ]
}
```

## Forecast

### `GET /api/deals/forecast/`

| Query param | Default | Notes |
|---|---|---|
| `tz` | server `TIME_ZONE` | IANA zone, same handling as the dashboard. Decides which calendar month "this month" is. Unknown zone: `400`. |
| `owner_id` | – | UUID. Limits every number to that owner. |

Definitions (non-deleted deals only):

- **open_pipeline**: sum of `amount` of deals whose stage is not `Won` or `Lost`.
- **weighted_forecast**: sum of `amount * probability / 100` over the same
  deals. Computed in the database with the deal's **own** `probability` (not the
  stage default) and rounded to 2 decimals once, at the end (half up).
- **open_deal_count**: number of those open deals.
- **won_this_month / lost_this_month**: sum of `amount` of `Won` / `Lost` deals
  whose `closed_at` is in the current calendar month in `tz`
  (`[first day 00:00, next month 00:00)` local time).
- **by_stage**: the open stages in stage order, zero rows included.
- **by_month**: open deals grouped by `expected_close_date` month (`"YYYY-MM"`),
  oldest first; deals without a close date are one row with `"month": null`,
  last.

```json
{
  "open_pipeline": "505000.00",
  "weighted_forecast": "275500.00",
  "won_this_month": "80000.00",
  "lost_this_month": "0.00",
  "open_deal_count": 5,
  "by_stage": [
    { "stage": "New", "count": 2, "total_amount": "80000.00", "weighted_amount": "8000.00" },
    { "stage": "Quotation Sent", "count": 1, "total_amount": "100000.00", "weighted_amount": "40000.00" },
    { "stage": "Negotiation", "count": 2, "total_amount": "325000.00", "weighted_amount": "227500.00" }
  ],
  "by_month": [
    { "month": "2026-11", "total_amount": "505000.00", "weighted_amount": "275500.00" }
  ]
}
```

## Creating a deal while converting a lead

`POST /api/leads/{id}/convert/` accepts an optional `deal` object. **Without a
`deal` key (or with `"deal": null`) nothing changes.**

```json
{
  "account_action": "create_new",
  "contact_action": "create_new",
  "deal": {
    "name": "Website for Ravi's shop",
    "amount": "100000.00",
    "expected_close_date": "2026-11-30",
    "stage": "Quotation Sent",
    "probability": 45,
    "description": "Brochure site"
  }
}
```

| `deal` field | Notes |
|---|---|
| `name` | required, max 255 |
| `amount` | decimal `>= 0`, default `0` |
| `expected_close_date` | optional date |
| `stage` | default `New`; only `New`, `Quotation Sent`, `Negotiation` (`Won` / `Lost` are rejected) |
| `probability` | optional integer 0–100, defaults from the stage |
| `description` | optional |

The deal is created **in the same transaction** as the account and contact,
after them and before the lead is marked converted. If it fails, the whole
conversion rolls back: the lead is not converted and no account, contact, deal
or timeline event remains.

- `owner_id` = the lead's owner; `created_by_id` = the user converting;
  `source_lead_id` = the lead; `lead_source` copied from the lead.
- `account_id` / `contact_id` are the account and contact of the conversion
  (created or existing). A lead without a company has no account, so the deal
  links the contact only.
- If an existing contact belongs to a different account than the one used for
  the conversion, the deal is rejected with `400` (the same request without a
  `deal` still succeeds).
- Records `DEAL_CREATED` with `metadata.source = "LEAD_CONVERSION"`,
  `source_lead_id`, `source_lead_name` (plus `deal_id`, `name`, `stage`),
  targeting the deal, the contact and the account (when present), so it also
  appears on the contact and account timelines.
- Response: `{"message": "Lead converted successfully."}`, plus
  `"deal_id": "<uuid>"` **only when** a deal was created. Invalid `deal` data
  answers `400` in the same shape as the other conversion fields
  (`{"deal": {"amount": ["..."]}}`).
