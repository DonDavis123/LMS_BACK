# Platform Companies API

Base path: `/api/platform/companies/`

Every endpoint requires `Authorization: Bearer <access_token>` of a **PLATFORM_SUPERADMIN** user
(no company). Anyone else gets `403 {"detail": "Only platform superadmins can do this."}`;
no/invalid token gets `401`.

Errors from use cases are `{"detail": "<message>"}` with `400` (validation/business rule) or
`404` (`"Company not found."`). Serializer validation errors are DRF's standard
`{"field": ["message", ...]}` with `400`.

Status values: `ONBOARDING`, `ACTIVE`, `SUSPENDED`. Timestamps are ISO 8601.

---

## GET `/`  — list companies

Query params (all optional): `search` (name or slug, case-insensitive), `status`
(`ONBOARDING|ACTIVE|SUSPENDED`), `sort_by` (`name|slug|status|created_at|users_count`),
`sort_direction` (`asc|desc`), `page` (default 1), `page_size` (default 20, max 50).
The JSON `filters` param used by `/api/users/` also works for `status`
(e.g. `[{"field":"status","operator":"in","value":["ACTIVE"]}]`).
Default order: newest first.

`200`
```json
{
  "results": [
    {
      "id": "uuid", "name": "Acme Corp", "slug": "acme-corp",
      "website": "https://acme.example.com", "status": "ACTIVE",
      "created_at": "2026-10-15T10:00:00Z", "users_count": 3
    }
  ],
  "pagination": {"page": 1, "page_size": 20, "total": 1, "total_pages": 1}
}
```
`users_count` excludes retired (deleted) users. `400` for an invalid status, sort field, page, etc.

---

## POST `/`  — create company + first SUPERADMIN (one transaction)

Request
```json
{
  "company_name": "Acme Corp",
  "website": "https://acme.example.com",
  "admin_name": "Alice Admin",
  "admin_email": "alice@acme.example.com",
  "admin_password": "at-least-8-chars"
}
```
`website` optional (may be omitted, `""` or `null`). `admin_password` min 8 chars, not trimmed.
The slug is generated from `company_name`; on a clash `-2`, `-3`, … is appended.
The company is created `ACTIVE`.

`201`
```json
{
  "company": {
    "id": "uuid", "name": "Acme Corp", "slug": "acme-corp",
    "website": "https://acme.example.com", "status": "ACTIVE", "status_reason": "",
    "status_changed_at": "…", "created_at": "…", "updated_at": "…"
  },
  "admin": {
    "id": "uuid", "name": "Alice Admin", "email": "alice@acme.example.com",
    "role": "SUPERADMIN", "is_active": true, "created_at": "…", "updated_at": "…"
  }
}
```
Errors: `400 {"detail": "User with this email already exists."}` (emails are unique across all
companies, case-insensitive; nothing is created), or field errors (short password, bad email,
bad URL, blank names).

---

## GET `/{company_id}/`  — detail

`200`
```json
{
  "id": "uuid", "name": "Acme Corp", "slug": "acme-corp", "website": null,
  "status": "SUSPENDED", "status_reason": "Unpaid invoice",
  "status_changed_at": "…", "created_at": "…", "updated_at": "…",
  "users_count": 3,
  "superadmins": [
    {"id": "uuid", "name": "Alice Admin", "email": "alice@acme.example.com", "is_active": true}
  ]
}
```
`404 {"detail": "Company not found."}`

---

## PATCH `/{company_id}/`  — update name and/or website

Request: `{"name": "New name", "website": "https://new.example.com"}` — at least one field.
`website: ""` or `null` clears it. The slug never changes.

`200` company object (same shape as `company` in the create response).
`400` if no field is given or `name` is blank; `404` unknown company.

---

## POST `/{company_id}/suspend/`

Request: `{"reason": "Unpaid invoice"}` (required, non-blank)

Sets `SUSPENDED`, stores the reason, `status_changed_at`/`status_changed_by`, and revokes all
refresh tokens of every user in the company.

`200` company object. `400 {"detail": "Company is already suspended."}`, `400` for a missing/blank
reason, `404` unknown company.

Effects on the company's users:
* login → `403 {"detail": "Your company account is suspended."}` (only after a correct password;
  a wrong password is still `401 Invalid email or password.`)
* any company endpoint with an existing access token → `403 {"detail": "Your company account is suspended."}`
* `/api/auth/refresh/` → `401`
* `GET /api/users/me/` still works and shows `company.status = "SUSPENDED"`, so the UI can show a notice.

## POST `/{company_id}/activate/`

No body. Sets `ACTIVE`, clears `status_reason`, updates `status_changed_at`/`status_changed_by`.

`200` company object. `400 {"detail": "Company is already active."}`, `404` unknown company.
(A company in `ONBOARDING` can be activated.) Users must log in again after reactivation.

---

## GET `/api/users/me/` (changed, backward compatible)

Adds `company`:
```json
{"id": "uuid", "name": "…", "email": "…", "role": "ADMIN",
 "company": {"id": "uuid", "name": "Acme Corp", "status": "ACTIVE"}}
```
`company` is `null` for platform admins.
