# Platform Admin API (phase 2)

Extends `docs/platform-companies-api.md`. All endpoints need a **PLATFORM_SUPERADMIN** access token.
Others: `403 {"detail": "Only platform superadmins can do this."}`; no token: `401`.
Use-case errors: `{"detail": "..."}` with `400`, or `404` for `"Company not found."` / `"User not found."`.
Serializer errors: `{"field": ["message"]}` with `400`. List shape:
`{"results": [...], "pagination": {"page", "page_size", "total", "total_pages"}}` (page_size default 20, max 50).

A suspended company can still be managed through these endpoints.

---

## Company users — `/api/platform/companies/{company_id}/users/`

### GET — list the company's users
Query (all optional): `search` (name/email), `role` (`SUPERADMIN|ADMIN|...`), `is_active` (`true|false`),
`sort_by` (`name|email|role|is_active|created_at`), `sort_direction` (`asc|desc`), `page`, `page_size`.
The JSON `filters` param of `/api/users/` also works. Retired (deleted) users are not listed.

`200`
```json
{"results": [{"id": "uuid", "name": "Bob", "email": "bob@acme.example.com",
              "role": "ADMIN", "is_active": true, "created_at": "…"}],
 "pagination": {"page": 1, "page_size": 20, "total": 1, "total_pages": 1}}
```
`400` invalid role/is_active/sort/page · `404 "Company not found."`

### POST — create a user in the company
```json
{"name": "Bob", "email": "bob@acme.example.com", "password": "min-8-chars", "role": "ADMIN"}
```
`role`: `SUPERADMIN` or `ADMIN` only. Password min 8, not trimmed.

`201` `{"id","name","email","role","is_active","created_at","updated_at"}`
`400 {"detail": "User with this email already exists."}` (unique across ALL companies, case-insensitive),
`400` field errors (bad role, short password, bad email) · `404 "Company not found."`

### POST `{user_id}/reset-password/`
`{"new_password": "min-8-chars"}` → `204` no body. Revokes all of the user's refresh tokens.
`400` validation, or `"A deleted user's password cannot be reset."` · `404 "User not found."`

### POST `{user_id}/block/` and `{user_id}/unblock/`
No body → `200` user object (`is_active` false/true). Block also revokes the user's sessions.
`400 "A deleted user cannot be blocked."` / `"...unblocked."` · `404 "User not found."`

`404 "User not found."` is also returned when the user belongs to another company or is a platform admin.

---

## Audit trail — `GET /api/platform/audit-logs/`
Query: `company_id` (UUID), `action`, `page`, `page_size`. Newest first.

Actions: `COMPANY_CREATED`, `COMPANY_UPDATED`, `COMPANY_SUSPENDED`, `COMPANY_ACTIVATED`,
`COMPANY_USER_CREATED`, `COMPANY_USER_PASSWORD_RESET`, `COMPANY_USER_BLOCKED`, `COMPANY_USER_UNBLOCKED`.

`200` results item:
```json
{"id": "uuid", "action": "COMPANY_SUSPENDED", "actor_id": "uuid", "actor_email": "platform@example.com",
 "company_id": "uuid", "target_user_id": null, "target_email": "",
 "metadata": {"reason": "Unpaid invoice"}, "created_at": "…"}
```
`metadata` by action: CREATED `{name, slug}` (target = first admin) · UPDATED `{changed_fields: ["name","website"]}` ·
SUSPENDED `{reason}` · ACTIVATED `{previous_status}` · USER_CREATED `{role}` · others `{}`.
Never contains passwords or tokens. `400` for an invalid `company_id`/`action`/page.

---

## Overview — `GET /api/platform/overview/`
`200`
```json
{"companies": {"total": 4, "active": 2, "onboarding": 1, "suspended": 1},
 "users": {"total": 3, "active": 2},
 "recent_companies": [{"id": "uuid", "name": "Acme", "status": "ACTIVE", "created_at": "…"}]}
```
Extra fields for the dashboard charts:
```json
{"companies_growth": [{"month": "2026-05", "count": 1}],
 "users_by_role": [{"role": "ADMIN", "count": 2}],
 "top_companies": [{"id": "uuid", "name": "Acme", "status": "ACTIVE", "users_count": 12}]}
```
`companies_growth`: new companies per month for the last 6 months (oldest first, zero-filled). `users_by_role`: company users by role, largest first. `top_companies`: top 5 by user count.
`users` counts company users only (platform admins and retired users excluded). `recent_companies`: newest 5.
