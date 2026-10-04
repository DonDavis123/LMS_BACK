# Manage Users – API contract

Audience: the frontend developer building the **Manage Users** screens.
Everything below is verified by the integration test
`src/modules/users/test_user_management_flow_api.py`, which drives these exact
endpoints as a real, logged-in superadmin.

- Base URL (local): `http://127.0.0.1:8000`
- All bodies are JSON (`Content-Type: application/json`).
- All user ids are UUIDs.
- Timestamps are ISO-8601 with the server offset (default `Asia/Kolkata`,
  `+05:30`; storage is UTC).

## 1. Authentication and who may call what

Send the access token on every request:

```
Authorization: Bearer <access_token>
```

| Endpoint group | Who may call |
|---|---|
| `GET /api/users/me/` | any logged-in user |
| every other `/api/users/...` endpoint in this document | **SUPERADMIN only** |

Statuses that apply to **every** SUPERADMIN-only endpoint:

| Status | Body | When |
|---|---|---|
| 401 | `{"detail": "Authentication credentials were not provided."}` | no `Authorization` header |
| 401 | `{"detail": "Given token not valid for any token type", "code": "token_not_valid", "messages": [...]}` | expired or invalid access token – call `POST /api/auth/refresh/`, or go to login if that fails |
| 401 | `{"detail": "User is inactive", "code": "user_inactive"}` | the token's user was blocked or deleted – go to login |
| 403 | `{"detail": "Only superadmins can manage users."}` | logged in as ADMIN (or any non-superadmin) |

A user's role and active flag are read from the database on every request, so
a role change, block or deletion takes effect immediately even though the
access token itself lives 15 minutes.

Show the **Manage Users** button only when `GET /api/users/me/` returns
`"role": "SUPERADMIN"`.

### Auth endpoints used by the flow

#### `POST /api/auth/login/` – public

Request:

```json
{ "email": "superadmin@example.com", "password": "password123" }
```

200 (the refresh token is set as an HttpOnly cookie, never in the JSON):

```json
{ "access_token": "eyJhbGciOi...", "token_type": "Bearer" }
```

| Status | Body |
|---|---|
| 400 | `{"email": ["Enter a valid email address."]}` / `{"password": ["This field is required."]}` |
| 401 | `{"detail": "Invalid email or password."}` (wrong password, unknown e-mail, **or the password was just reset by a superadmin**) |
| 403 | `{"detail": "User account is inactive."}` (blocked **or deleted** user) |

E-mail matching is case-insensitive. Passwords are matched exactly as typed
(no trimming).

#### `POST /api/auth/refresh/` – public, needs the refresh cookie

200: `{"access_token": "...", "token_type": "Bearer"}` (cookie rotated).

| Status | Body |
|---|---|
| 401 | `{"detail": "Refresh token is missing."}` |
| 401 | `{"detail": "Invalid or expired refresh token."}` – also returned after the user's password was reset, the user was blocked, their role changed, or they were deleted |

---

## 2. Endpoints

### 2.1 Current user

`GET /api/users/me/` – any authenticated user

200:

```json
{
  "id": "3f6c1d1e-6a0e-4a43-9d57-0c7c4a0d2b11",
  "name": "Super Admin",
  "email": "superadmin@example.com",
  "role": "SUPERADMIN"
}
```

Roles: `SUPERADMIN`, `ADMIN`, `SALES_MANAGER`, `SALES_EXECUTIVE`.

| Status | Body |
|---|---|
| 401 | see section 1 |
| 404 | `{"detail": "User not found."}` |

---

### 2.2 List / search / filter users

`GET /api/users/` – SUPERADMIN

Deleted users are never listed. Query parameters (all optional):

| Param | Default | Notes |
|---|---|---|
| `search` | – | case-insensitive "contains" on name **or** e-mail, max 100 chars |
| `filters` | – | URL-encoded JSON array of `{"field","operator","value"}` (see below) |
| `sort_by` | – | `name`, `email`, `role`, `is_active`, `created_at` |
| `sort_direction` | `asc` with `sort_by`, otherwise newest first | `asc` \| `desc` |
| `page` | `1` | ≥ 1 |
| `page_size` | `20` | 1 – 50 |

Filterable fields and operators:

| Field | Operators | Value |
|---|---|---|
| `name`, `email` | `contains`, `not_contains`, `equals`, `not_equals`, `starts_with`, `ends_with` | non-empty string (case-insensitive) |
| `role` | `equals`, `not_equals`, `in`, `not_in` | a role string, or a non-empty list of role strings for `in`/`not_in` |
| `is_active` | `equals`, `not_equals` | `true` / `false` (JSON boolean) |

Example: `GET /api/users/?search=admin&page=1&page_size=20&filters=[{"field":"role","operator":"equals","value":"ADMIN"},{"field":"is_active","operator":"equals","value":true}]`

200:

```json
{
  "results": [
    {
      "id": "8d5a0a5e-0b53-4a8c-a0e4-2f4f9a3c7e10",
      "name": "Plain Admin",
      "email": "admin@example.com",
      "role": "ADMIN",
      "is_active": true,
      "created_at": "2026-10-05T01:40:12.481220+05:30"
    }
  ],
  "pagination": { "page": 1, "page_size": 20, "total": 1, "total_pages": 1 }
}
```

`total_pages` is `0` when there are no results.

| Status | Message (`{"detail": ...}`) |
|---|---|
| 400 | `page must be a valid integer.` / `page_size must be a valid integer.` |
| 400 | `page must be greater than or equal to 1.` / `page_size must be greater than or equal to 1.` |
| 400 | `Page size must be less than or equal to 50.` |
| 400 | `Search must be at most 100 characters.` |
| 400 | `The filters parameter must contain valid JSON.` / `The filters parameter must be a JSON array.` |
| 400 | `Filter at index N must be a JSON object.` / `... must contain a valid field.` / `... must contain a valid operator.` / `... must contain a value.` |
| 400 | `Filtering is not supported for field 'x'.` |
| 400 | `Operator 'x' is not supported for text field 'name'.` / `... for choice field 'role'.` |
| 400 | `Value for 'name' must be a string.` / `Value for 'name' cannot be empty.` |
| 400 | `Invalid value for choice field 'role'.` / `Value for 'role' must be a non-empty list of valid choices.` |
| 400 | `Value for boolean field 'is_active' must be true or false.` |
| 400 | `Sorting is not supported for field 'x'.` |
| 400 | `The sort_direction parameter must be 'asc' or 'desc'.` |
| 401 / 403 | see section 1 |

---

### 2.3 Profile page data

`GET /api/users/<id>/` – SUPERADMIN

200:

```json
{
  "id": "5b0f9c3e-2c61-4e0b-9a52-61f0c0a7a1d4",
  "name": "Target User",
  "email": "target@example.com",
  "role": "ADMIN",
  "is_active": true,
  "created_at": "2026-10-05T01:40:12.481220+05:30",
  "updated_at": "2026-10-05T01:40:12.481220+05:30"
}
```

`is_active: false` means blocked **or** deleted. A deleted user is still
readable by id (so old links do not 404) but never appears in the list.

| Status | Body |
|---|---|
| 404 | `{"detail": "User not found."}` |
| 401 / 403 | see section 1 |

---

### 2.4 Edit a user

`PATCH /api/users/<id>/` – SUPERADMIN

Send at least one field. Unknown fields are rejected.

| Field | Type | Rules |
|---|---|---|
| `name` | string | ≤ 150 chars, not blank (trimmed) |
| `email` | string | valid e-mail; stored lower-cased; unique, **case-insensitive** |
| `role` | string | `SUPERADMIN` or `ADMIN` only |

Request:

```json
{ "name": "Target Renamed", "email": "Renamed.Target@Example.com" }
```

200 (same shape as 2.3, e-mail normalised):

```json
{
  "id": "5b0f9c3e-2c61-4e0b-9a52-61f0c0a7a1d4",
  "name": "Target Renamed",
  "email": "renamed.target@example.com",
  "role": "ADMIN",
  "is_active": true,
  "created_at": "2026-10-05T01:40:12.481220+05:30",
  "updated_at": "2026-10-05T01:52:30.118904+05:30"
}
```

Changing `role` signs the user out everywhere (refresh tokens revoked).

| Status | Body |
|---|---|
| 400 | `{"detail": "User with this email already exists."}` |
| 400 | `{"detail": "A deleted user cannot be updated."}` |
| 400 | `{"detail": "A superadmin cannot change their own role."}` |
| 400 | `{"detail": "Users cannot be assigned the <ROLE> role."}` |
| 400 | `{"non_field_errors": ["At least one field is required for update."]}` |
| 400 | field errors, e.g. `{"email": ["Enter a valid email address."]}`, `{"name": ["This field may not be blank."]}`, `{"role": ["\"X\" is not a valid choice."]}`, `{"foo": ["This field is not allowed."]}` |
| 404 | `{"detail": "User not found."}` |
| 401 / 403 | see section 1 |

---

### 2.5 Reset a user's password

`POST /api/users/<id>/reset-password/` – SUPERADMIN

Request (8–128 chars, stored exactly as sent – spaces are not trimmed):

```json
{ "new_password": "NewPassw0rd!" }
```

204, empty body. The old password stops working immediately and all of the
user's refresh tokens are revoked. The password is never logged.

| Status | Body |
|---|---|
| 400 | `{"new_password": ["Ensure this field has at least 8 characters."]}` (also `"This field is required."`, `"Ensure this field has no more than 128 characters."`) |
| 400 | `{"detail": "Use the forgot-password flow to change your own password."}` |
| 400 | `{"detail": "A deleted user's password cannot be reset."}` |
| 404 | `{"detail": "User not found."}` |
| 401 / 403 | see section 1 |

---

### 2.6 Block / unblock

`POST /api/users/<id>/block/` and `POST /api/users/<id>/unblock/` – SUPERADMIN

No request body. Both return 200 with the user (shape of 2.3). Block sets
`is_active: false`, revokes all refresh tokens, and the user's next login is
rejected with `403 User account is inactive.`. Unblock restores login (the user
must log in again).

```json
{
  "id": "5b0f9c3e-2c61-4e0b-9a52-61f0c0a7a1d4",
  "name": "Target Renamed",
  "email": "renamed.target@example.com",
  "role": "ADMIN",
  "is_active": false,
  "created_at": "2026-10-05T01:40:12.481220+05:30",
  "updated_at": "2026-10-05T01:55:02.774310+05:30"
}
```

| Status | Body |
|---|---|
| 400 | block: `{"detail": "A superadmin cannot block their own account."}` |
| 400 | block: `{"detail": "A deleted user cannot be blocked."}` |
| 400 | unblock: `{"detail": "A deleted user cannot be unblocked."}` |
| 404 | `{"detail": "User not found."}` |
| 401 / 403 | see section 1 |

---

### 2.7 Deletion preview

`GET /api/users/<id>/deletion-preview/` – SUPERADMIN. Read-only.

200:

```json
{
  "user": {
    "id": "5b0f9c3e-2c61-4e0b-9a52-61f0c0a7a1d4",
    "name": "Target Renamed",
    "email": "renamed.target@example.com"
  },
  "impact": {
    "leads": 2,
    "contacts": 1,
    "accounts": 1,
    "tasks": 2,
    "meetings": 1,
    "reminders": 2,
    "notifications": 1,
    "timeline": 1
  },
  "transfer_required": {
    "leads": true,
    "contacts": true,
    "accounts": true,
    "meetings": true
  },
  "permanent_deletions": { "tasks": 2, "reminders": 2, "notifications": 1 },
  "user_action": { "type": "SOFT_DELETE" },
  "can_retire": true,
  "blockers": [],
  "has_related_data": true,
  "user_is_blocked": false,
  "available_actions": ["BLOCK", "TRANSFER_AND_DELETE"]
}
```

How to read it:

- `impact.meetings` counts meetings the user **hosts**. Meetings they only
  attend are not counted and are not changed.
- `transfer_required.*` = the user owns/hosts at least one of that kind. If any
  is `true`, deletion **needs** a `replacement_user_id`. Leads, contacts,
  accounts and hosted meetings move to the replacement.
- `permanent_deletions` = tasks, reminders and notifications of the user are
  deleted for good (no replacement involved).
- `impact.timeline` is informational: timeline history is always kept.
- `available_actions`: `BLOCK` is absent when the user is already blocked;
  both are absent (and `can_retire` is `false`, `blockers` lists why) when the
  target is the logged-in superadmin themself.
- `has_related_data` is `true` when any of leads, contacts, accounts, meetings,
  tasks, reminders or notifications exist.

| Status | Body |
|---|---|
| 400 | `{"detail": "User has already been deleted."}` |
| 404 | `{"detail": "User not found."}` |
| 401 / 403 | see section 1 |

---

### 2.8 Replacement candidates

`GET /api/users/<id>/replacement-candidates/` – SUPERADMIN

Active `ADMIN`/`SUPERADMIN` users except the user being deleted, ordered by
name. Blocked, deleted and sales-role users are excluded.

200:

```json
[
  {
    "id": "8d5a0a5e-0b53-4a8c-a0e4-2f4f9a3c7e10",
    "name": "Plain Admin",
    "email": "admin@example.com",
    "role": "ADMIN"
  },
  {
    "id": "3f6c1d1e-6a0e-4a43-9d57-0c7c4a0d2b11",
    "name": "Super Admin",
    "email": "superadmin@example.com",
    "role": "SUPERADMIN"
  }
]
```

The list is a plain array (not paginated) and may be empty.

| Status | Body |
|---|---|
| 400 | `{"detail": "User has already been deleted."}` |
| 404 | `{"detail": "User not found."}` |
| 401 / 403 | see section 1 |

---

### 2.9 Delete (retire) a user

`DELETE /api/users/<id>/` – SUPERADMIN

Request body (JSON object, optional when nothing needs transferring):

```json
{ "replacement_user_id": "8d5a0a5e-0b53-4a8c-a0e4-2f4f9a3c7e10" }
```

`replacement_user_id` may be omitted or `null` only when every
`transfer_required` flag is `false`. If it **is** sent it is always validated.

204, empty body. Effects (all-or-nothing, one transaction):

- The user row is kept, marked deleted and inactive; the e-mail stays reserved.
- Leads, contacts, accounts and hosted meetings now belong to the replacement.
  `created_by` / `modified_by` and meeting participants are not touched;
  meetings the user merely attends keep their host.
- The user's tasks, reminders and notifications are permanently deleted.
- Timeline history stays.
- An audit entry `USER_RETIRED` records the replacement.
- All refresh tokens are revoked; login returns `403 User account is inactive.`

| Status | Body |
|---|---|
| 400 | `{"detail": "A superadmin cannot delete their own account."}` |
| 400 | `{"detail": "User has already been deleted."}` |
| 400 | `{"detail": "Replacement user is required."}` (records to transfer, no replacement sent) |
| 400 | `{"detail": "Replacement user must be different from the user being deleted."}` |
| 400 | `{"detail": "Replacement user has been deleted."}` |
| 400 | `{"detail": "Replacement user must be active."}` |
| 400 | `{"detail": "Replacement user must be an Admin or Superadmin."}` |
| 400 | `{"replacement_user_id": ["Must be a valid UUID."]}` / `{"<field>": ["This field is not allowed."]}` / `{"non_field_errors": ["Request body must be an object."]}` |
| 404 | `{"detail": "User not found."}` |
| 404 | `{"detail": "Replacement user not found."}` |
| 500 | `{"detail": "User could not be deleted."}` – database failure; everything was rolled back, safe to retry |
| 401 / 403 | see section 1 |

---

### 2.10 Audit log (verification of the above)

`GET /api/users/audit-logs/?user_id=<uuid>&action=<ACTION>&page=1&page_size=20` – SUPERADMIN

Newest first. Actions: `USER_CREATED`, `USER_UPDATED`, `USER_ROLE_CHANGED`,
`USER_BLOCKED`, `USER_UNBLOCKED`, `USER_PASSWORD_RESET`, `USER_RETIRED`.

200:

```json
{
  "results": [
    {
      "id": "0b6c2f8e-5f5d-4b8e-9f6d-7a1d2c3e4f50",
      "action": "USER_RETIRED",
      "actor_id": "3f6c1d1e-6a0e-4a43-9d57-0c7c4a0d2b11",
      "actor_email": "superadmin@example.com",
      "target_user_id": "5b0f9c3e-2c61-4e0b-9a52-61f0c0a7a1d4",
      "target_email": "renamed.target@example.com",
      "metadata": {
        "replacement_user_id": "8d5a0a5e-0b53-4a8c-a0e4-2f4f9a3c7e10",
        "replacement_user_email": "admin@example.com"
      },
      "created_at": "2026-10-05T02:03:44.902115+05:30"
    }
  ],
  "pagination": { "page": 1, "page_size": 20, "total": 5, "total_pages": 1 }
}
```

| Status | Body |
|---|---|
| 400 | `{"detail": "user_id must be a valid UUID."}` / `{"detail": "action is not a valid audit action."}` plus the paging messages from 2.2 |
| 401 / 403 | see section 1 |

### 2.11 Create user (same URL as the list; not part of the verified flow above)

`POST /api/users/` – SUPERADMIN. Body: `name`, `email`, `password` (≥ 8 chars,
not trimmed), `role` (`SUPERADMIN` | `ADMIN`). 201 returns the user (shape of
2.3). 400 `{"detail": "User with this email already exists."}` or field errors.

---

## 3. Delete-user dialog sequence

```
User clicks "Delete" on a profile / list row
        │
        ▼
GET /api/users/<id>/deletion-preview/
        │
        ├─ 400 "User has already been deleted." → close dialog, refresh list
        ├─ can_retire == false → show blockers[0], no actions
        │
        ▼
Show impact counts (impact.*) and the permanent_deletions warning.
Offer the buttons listed in available_actions:

  ┌───────────────┬───────────────────────────────────────────────────┐
  │ "BLOCK"       │ POST /api/users/<id>/block/  → 200, close dialog. │
  │ (only if the  │ Keeps all data; reversible with /unblock/.        │
  │ user is not   │                                                   │
  │ blocked)      │                                                   │
  ├───────────────┼───────────────────────────────────────────────────┤
  │ "TRANSFER_    │ if any transfer_required.* is true:               │
  │  AND_DELETE"  │   GET /api/users/<id>/replacement-candidates/     │
  │               │   → user picks one (list may be empty → disable)  │
  │               │ then DELETE /api/users/<id>/                      │
  │               │   {"replacement_user_id": "<picked id>"}          │
  │               │ if all transfer_required.* are false:             │
  │               │   DELETE /api/users/<id>/  (body {} or none)      │
  │               │ → 204: close dialog, refresh list                 │
  └───────────────┴───────────────────────────────────────────────────┘

DELETE errors to surface inline: 400/404 `detail` text (see 2.9).
On 500 keep the dialog open – nothing was changed.
```

Summary: **preview → (block) OR (candidates → delete)**.

## 4. Quick reference

| Purpose | Method and URL | Success |
|---|---|---|
| Who am I | `GET /api/users/me/` | 200 |
| List | `GET /api/users/` | 200 |
| Profile | `GET /api/users/<id>/` | 200 |
| Edit | `PATCH /api/users/<id>/` | 200 |
| Reset password | `POST /api/users/<id>/reset-password/` | 204 |
| Block | `POST /api/users/<id>/block/` | 200 |
| Unblock | `POST /api/users/<id>/unblock/` | 200 |
| Deletion preview | `GET /api/users/<id>/deletion-preview/` | 200 |
| Replacement candidates | `GET /api/users/<id>/replacement-candidates/` | 200 |
| Delete | `DELETE /api/users/<id>/` | 204 |
| Audit log | `GET /api/users/audit-logs/` | 200 |
