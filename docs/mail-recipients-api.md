# Mail recipients API

Turns a selection made on a list screen into a clean, deduplicated list of
recipients plus Bcc batches. The server sends nothing: the browser opens a
prefilled Gmail compose tab per batch. Gmail URLs are length-limited, so a
batch holds at most 50 addresses (default 40).

```
POST /api/mail/recipients/resolve/
```

Permissions: `IsAuthenticated` + `IsCompanyUser`. The company always comes from
the signed-in user; any company id in the body is ignored.

## Request

```json
{
  "entity": "contacts",
  "selection": {"mode": "ids", "ids": ["<uuid>"]},
  "include_secondary_email": false,
  "batch_size": 40
}
```

or, for "everything matching the current search/filters":

```json
{
  "entity": "contacts",
  "selection": {
    "mode": "filter",
    "search": "acme",
    "filters": [{"field": "department", "operator": "equals", "value": "Sales"}],
    "exclude_ids": ["<uuid>"]
  }
}
```

| Field | Rules |
|-------|-------|
| `entity` | `contacts`, `leads` or `accounts` |
| `selection.mode = ids` | `ids`: 1 to **500** UUIDs (counted as sent; repeats are looked up and counted once) |
| `selection.mode = filter` | `search` (string or null, max 100 chars), `filters` (same JSON array as the list's `filters` parameter, may be null/empty), `exclude_ids` (optional, max 2000 UUIDs) |
| `include_secondary_email` | boolean, default `false` |
| `batch_size` | whole number 1..50, default 40 |

Filter mode reads through the entity's own list use case (as the `exports`
module does): same search, same filter validation and error messages, same
company scoping and soft-delete rules, all pages. More than **2000** matches is
refused with 400 (checked on the matches, before `exclude_ids` is applied).
Order is the list's default order (newest first); `ids` mode keeps the order
of the ids sent.

## Response 200

```json
{
  "entity": "contacts",
  "summary": {"selected": 12, "eligible": 9, "skipped": 3, "batches": 1},
  "recipients": [
    {"record_id": "<uuid>", "record_type": "CONTACT", "name": "Ann Alpha",
     "email": "Ann@Acme.test", "email_kind": "PRIMARY",
     "account_name": "Acme Corp", "source_account_id": null}
  ],
  "skipped": [
    {"record_id": "<uuid>", "record_type": "CONTACT", "name": "Out Out",
     "reason": "OPTED_OUT"}
  ],
  "batches": [["ann@acme.test", "b@y.com"], ["c@z.com"]]
}
```

* `selected`: records selected (accounts for `accounts`; filter mode: matches
  minus `exclude_ids`). `eligible`: addresses in `recipients`. `skipped`:
  entries in `skipped`. `batches`: number of batches. For accounts, and with
  secondary emails, `selected` is not `eligible + skipped`.
* `recipients[].email` is shown as stored (trimmed); `batches` hold the
  lower-cased eligible addresses, in recipient order, chunked by `batch_size`.
* `record_type` of a recipient is `CONTACT` or `LEAD`; of a skipped entry
  `CONTACT`, `LEAD` or `ACCOUNT`.

## Rules

| Entity | Resolution |
|--------|-----------|
| contacts | `email_opt_out` -> `OPTED_OUT`; no email -> `NO_EMAIL`; fails Django `validate_email` -> `INVALID_EMAIL`. With `include_secondary_email`, a valid `secondary_email` is an extra recipient (`email_kind` `SECONDARY`). |
| leads | Same, without the opt-out check (leads have no such flag, and no secondary email). |
| accounts | An account has no email: it resolves to its contacts (`get_by_account_id_with_owner`, non-deleted), each with the contact rules, `source_account_id` = the account. An account with no contacts is skipped with `NO_CONTACTS`. |

Across the whole result addresses are compared case-insensitively: the first
is kept, later ones are reported `DUPLICATE_EMAIL` (a secondary equal to an
address already taken is reported too). Opt-out wins over every other check
and blocks the secondary email as well. A missing/malformed secondary email is
ignored silently. A contact with a bad primary but a valid secondary (when
requested) appears both in `skipped` (primary problem) and `recipients`.

Ids that do not exist, are soft-deleted or belong to another company are all
reported identically: `NOT_FOUND`, `name` `""`, the entity's record type.

## Authorisation

Mirrors the existing read rules:

| Entity / mode | Who |
|---------------|-----|
| contacts, accounts (both modes) | any company user |
| leads, `filter` | SUPERADMIN and ADMIN only (`LeadPermissions.can_view_all_leads`, as `GET /api/leads/` and `GET /api/exports/leads/`) |
| leads, `ids` | any company user (as the lead detail `GET /api/leads/<id>/`) |

Converted leads: not in the lead list (so not in filter mode) but readable by
id like the lead detail, so `ids` mode includes them.

## Errors

| Status | When |
|--------|------|
| 400 `{"detail": "..."}` | invalid body, unknown entity/mode, bad UUID, empty ids, >500 ids, >2000 `exclude_ids`, `batch_size` outside 1..50, invalid filters/search (same messages as the list), more than 2000 matches |
| 401 | not signed in |
| 403 | platform superadmin / no company / suspended company; non-admin leads `filter` |

Examples of `detail`: `ids mode accepts at most 500 ids.`,
`batch_size must be between 1 and 50.`,
`Filtering is not supported for field 'bogus'.`,
`This selection matches 2001 records, more than the limit of 2000. Narrow the search or filters and try again.`

Postman requests: `postman/collections/LMS/mail/`.
