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

---

## Public endpoints

No login. Base path `/api/public/lead-forms/<token>/` where `<token>` is the
form's `public_token`. JWT authentication is disabled on these views, so a
missing, expired or invalid `Authorization` header is ignored. The company is
always resolved from the token; nothing about company or user is read from the
request body.

### GET `/api/public/lead-forms/<token>/`

`200`
```json
{"title": "Contact us", "company_name": "Acme", "accepting_responses": true}
```
`accepting_responses` is `false` when the form is blocked, not configured or has
no eligible owner (still `200`). Nothing else is returned. Unknown token: `404`.

### POST `/api/public/lead-forms/<token>/`

All fields required, trimmed, no unknown fields:

```json
{"name": "Jane Doe", "email": "jane@example.com", "phone": "9876543210", "description": "I would like a demo."}
```

Limits: `name` 150, `email` 254 (valid email), `phone` 20, `description` 2000.

| Status | Body |
|---|---|
| `201` | `{"detail": "Thanks, we've received your details."}` (no lead data, no ids) |
| `400` | field errors, e.g. `{"email": ["Enter a valid email address."]}` or `{"field": ["Unknown field."]}` |
| `404` | `{"detail": "Not found."}` (unknown token) |
| `410` | `{"detail": "This form is no longer accepting responses"}` (blocked, not configured, no eligible owner or the lead source is no longer a valid option; the reason is not revealed) |

The lead is created with the form's `lead_source`, `description` = the visitor's
message only, and an owner chosen by the form: the single owner, or the next
eligible rotation owner after `last_assigned_position` (wrapping around).
Each submission locks the form row, so concurrent submissions rotate correctly;
`submission_count` and `last_submission_at` are updated in the same transaction.

### Protection against abuse

**Throttling (per client IP).** Only the public form is throttled; no other
endpoint is.

| Request | Scope | Default rate | Environment variable |
|---|---|---|---|
| `POST` | `lead_capture_submit` | `10/hour` | `LEAD_CAPTURE_SUBMIT_RATE` |
| `GET` | `lead_capture_view` | `120/hour` | `LEAD_CAPTURE_VIEW_RATE` |

Over the limit the API answers `429` in the usual error shape, with a
`Retry-After` header (seconds):

```json
{"detail": "Request was throttled. Expected available in 1800 seconds."}
```

*Client IP behind a proxy.* The app runs behind a reverse proxy, so the real IP
comes from `X-Forwarded-For`. Set the environment variable `NUM_PROXIES` to the
exact number of proxies in front of the app (it is `None` by default). If it is
unset behind a proxy, DRF trusts the whole header (which a client can forge) or,
without the header, every visitor shares the proxy's address and one limit.

*Per-process limits.* Counters are kept in Django's cache. The default cache is
per process, so with several workers each process counts on its own and the
effective limit is roughly rate x number of processes. A shared cache (for
example Redis) is needed for an exact global limit.

**Daily cap per form.** A form accepts at most `LEAD_CAPTURE_DAILY_CAP` leads
per local day (default `500`; the day follows the project `TIME_ZONE`). After
that, `POST` answers `410` with the same body as a closed form,
`{"detail": "This form is no longer accepting responses"}`, until the next day.
The count is kept on the form (`daily_submission_count`, `daily_submission_date`)
and only counts accepted submissions. `GET` still returns `accepting_responses:
true`, so the cap is only discovered on submit.

**Request format and size.** The public view accepts JSON only
(`Content-Type: application/json`); other content types are answered `415`.
A request whose `Content-Length` is above 10 KB (10240 bytes) is answered `413`
(`{"detail": "The request is too large."}`) before the body is read. A body sent
without `Content-Length` (chunked) is not caught by this check.

**Frontend states**

- *Closed* (`GET` has `accepting_responses: false`, or `POST` returns `410`):
  replace the form with a message such as "This form is no longer accepting
  responses". Do not offer a retry; this also covers the daily cap.
- *Too many requests* (`429`): keep the visitor's input, show "Too many
  requests, please try again later", and disable the submit button for the
  `Retry-After` seconds.
- *Thank you* (`201`): hide the form and show the `detail` message (or your own
  text). Do not resubmit on refresh.
- `413` and `415` should not happen with the normal form; show a generic error.
