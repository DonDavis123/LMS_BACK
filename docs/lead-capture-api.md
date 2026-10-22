# Lead Capture Form API (management)

Base path: `/api/lead-capture/`

Every company has **exactly one** lead capture form. Its public link
(`{FRONTEND_URL}/lead/{public_token}`) is meant to be shared as a link or a QR
code. The QR **image is drawn by the frontend** from `public_url`; the backend
never generates or stores images. The public submission endpoints are not part
of this document (they come in a later part).

All endpoints below are **management** endpoints:

- `Authorization: Bearer <access_token>` of a **SUPERADMIN** of the company.
  The company always comes from the token, never from the request, so a
  superadmin can only ever see and change their own company's form.
- Any other user gets `403 {"detail": "Only company superadmins can manage the lead capture form."}`
  (or `"A company account is required."` for platform superadmins) and **never receives the token**.
  No/invalid token gets `401`.
- A suspended company gets `403` like every other company endpoint.

Errors from business rules are `{"detail": "<message>"}` with `400`. Serializer
validation errors are DRF's standard `{"field": ["message", ...]}` with `400`.
Timestamps are ISO 8601.

---

## Where the form comes from

- **New company:** the form is created in the *same transaction* as the company
  (`POST /api/platform/companies/`). If it cannot be created, the company is not
  created either.
- **Existing companies:** migration `lead_capture.0002_backfill_lead_forms` gave
  each one a form (idempotent, a different token per company).
- Every new form starts **blocked** (`is_active: false`) and **not configured**
  (no lead source, no owner). It must be configured before it can be unblocked.
- Safety net: if a company somehow has no form, `GET`/`PATCH` create the default
  one on first use instead of failing.

## The form object

```json
{
  "id": "uuid",
  "title": "Contact us",
  "lead_source": "Web Research",
  "assignment_mode": "ROTATION",
  "single_owner": {"id": "uuid", "name": "Alice Admin"},
  "rotation_owners": [
    {"id": "uuid", "name": "Alice Admin", "position": 0},
    {"id": "uuid", "name": "Bob Admin", "position": 1}
  ],
  "is_active": true,
  "is_configured": true,
  "needs_attention": false,
  "public_token": "Zr3k...(32 chars)",
  "public_url": "https://app.example.com/lead/Zr3k...",
  "submission_count": 0,
  "last_submission_at": null,
  "created_at": "2026-10-22T10:00:00Z",
  "updated_at": "2026-10-22T10:00:00Z"
}
```

| Field | Notes |
|---|---|
| `lead_source` | One of the company's active **Lead Source** options (the same picklist and validation Leads use, `/api/picklists/leads/lead_source/`). `null` = not chosen yet. |
| `assignment_mode` | `SINGLE_OWNER` (default) or `ROTATION`. |
| `single_owner` | Used when mode is `SINGLE_OWNER`. May still be filled while mode is `ROTATION` (kept for switching back). |
| `rotation_owners` | Ordered, `position` starts at 0. Used when mode is `ROTATION`. |
| `is_active` | `false` = **blocked**. |
| `is_configured` | **Computed live, not stored.** `true` when `lead_source` is set **and** the active mode has at least one eligible owner. |
| `needs_attention` | `true` when the form is **live** (`is_active`) but **not configured** — e.g. its only owner was deactivated. The form keeps working as a record; nothing breaks. |
| `public_token` | Unguessable (`secrets.token_urlsafe(24)`), never derived from an id. |
| `public_url` | `{FRONTEND_URL}/lead/{public_token}` (trailing `/` of `FRONTEND_URL` is stripped). Encode this in the QR code. |
| `submission_count`, `last_submission_at` | Maintained by the public endpoints (later part). |

**Eligible owner** = the same rule as the leads "lead owners" lookup
(`GET /api/lead-owners/`): an **active**, **not deleted** user of **this
company** with role **ADMIN** or **SUPERADMIN**.

---

## GET `form/` — the company's form

`200` the form object.

## PATCH `form/` — update settings

Send only what changes. Unknown fields are rejected.

```json
{
  "title": "Talk to sales",
  "lead_source": "Web Research",
  "assignment_mode": "ROTATION",
  "single_owner_id": null,
  "rotation_owner_ids": ["uuid-1", "uuid-2"]
}
```

| Field | Rules |
|---|---|
| `title` | Text, whitespace collapsed, 1–150 chars. |
| `lead_source` | An active Lead Source option (matched case-insensitively and stored in its canonical spelling). `null`, `""` or the built-in `"None"` clear it. |
| `assignment_mode` | `SINGLE_OWNER` or `ROTATION`. |
| `single_owner_id` | UUID of an eligible owner, or `null` to clear. |
| `rotation_owner_ids` | Non-empty ordered list (max 50), no duplicates, all eligible. The list order is the rotation order; changing it restarts the rotation. |

Rules:

- A draft can be saved piece by piece (e.g. just `title`). As soon as you send
  `assignment_mode`, `single_owner_id` or `rotation_owner_ids`, the resulting
  setup must be complete for the active mode: `SINGLE_OWNER` needs an eligible
  `single_owner_id`; `ROTATION` needs at least one eligible owner.
- Unknown, other-company, inactive, deleted or wrong-role owners are all rejected
  with the same message (nothing is revealed about other companies).
- **Design choice:** an edit that would turn a *configured, live* form into an
  unconfigured one (e.g. clearing `lead_source`) is **rejected with `400`** —
  it is never auto-blocked. Block the form first, then edit.
- The request is atomic: if any part is invalid nothing is changed.

`200` the updated form object.

Errors (`400`, `{"detail": ...}` unless noted):

| Message |
|---|
| `"X" is not a valid option for Lead Source.` / `"X" is no longer available for Lead Source. Choose another option.` |
| `Selected owner must be an active ADMIN or SUPERADMIN of this company.` |
| `single_owner_id is required when assignment_mode is SINGLE_OWNER.` |
| `rotation_owner_ids needs at least one owner when assignment_mode is ROTATION.` |
| `rotation_owner_ids cannot contain the same user twice.` |
| `This change would leave the live form without a lead source or an eligible owner. Block the form first.` |
| `{"field": ["Unknown field."]}` for unknown fields; `{"non_field_errors": ["Provide at least one field to update."]}` for an empty body |

## POST `form/block/`

Blocks the form (`is_active: false`). Idempotent. `200` the form object.

## POST `form/unblock/`

Makes the form live. `200` the form object. While the form is not configured:

`400`
```json
{"detail": "Set a lead source and at least one eligible owner before unblocking the form."}
```

## POST `form/regenerate-link/`

Generates a new `public_token`; the **old link stops working immediately** (as
soon as the request commits). Works whether the form is blocked or live and does
not change its state. `200` the form object with the new `public_token` / `public_url`.

---

## Concurrency

`PATCH`, `block`, `unblock` and `regenerate-link` run in a transaction that locks
the company's form row (`SELECT … FOR UPDATE`), so two simultaneous calls are
applied one after the other and never overwrite each other. Counters
(`submission_count`, `last_submission_at`) are not touched by these endpoints.

## Notes for the frontend

- `public_url` is `"/lead/<token>"` (no host) if `FRONTEND_URL` is not configured on the server.
- Show a warning when `needs_attention` is `true` and offer to fix the owners or block the form.
- Owner choices come from `GET /api/lead-owners/`; lead source choices from `GET /api/picklists/leads/lead_source/`.
