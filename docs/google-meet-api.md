# Google Meet for meetings

Meetings can get a Google Meet link, and every participant is emailed a
Google Calendar invite. Google sends the invite, every later update and the
cancellation, from the **host's own Gmail** (`sendUpdates=all`). The CRM's own
mailing module is not involved.

The calendar event always lives on the **meeting host's** Google calendar, so
the host must have connected their Google account.

## Environment variables

| Variable | Purpose |
| --- | --- |
| `GOOGLE_CLIENT_ID` | OAuth client ID (type *Web application*) |
| `GOOGLE_CLIENT_SECRET` | OAuth client secret |
| `GOOGLE_REDIRECT_URI` | Exactly `https://<backend>/api/integrations/google/callback/` (also register a localhost one for development) |
| `GOOGLE_TOKEN_ENCRYPTION_KEY` | Fernet key that encrypts refresh tokens at rest |
| `FRONTEND_URL` | Already used elsewhere; the browser returns here after consent |
| `GOOGLE_FRONTEND_RETURN_PATH` | Optional. Default `/integrations/google/callback` |
| `GOOGLE_OAUTH_STATE_MAX_AGE` | Optional. Seconds the signed OAuth state is valid. Default `600` |
| `GOOGLE_API_TIMEOUT` | Optional. Seconds before a Google call gives up. Default `15` |

Generate the encryption key once and keep it safe (losing it means users must
reconnect):

```
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Required OAuth scopes: `openid`, `email`,
`https://www.googleapis.com/auth/calendar.events`.

## Connection endpoints

All except the callback need the normal `Authorization: Bearer <JWT>` header.

### `GET /api/integrations/google/status/`

```json
{
  "configured": true,
  "connected": true,
  "status": "connected",
  "google_email": "me@gmail.com",
  "connected_at": "2026-11-14T10:00:00Z"
}
```

`status` is `connected` or `revoked` (token revoked or expired; reconnect).
`configured: false` means the server env vars above are missing.

### `POST /api/integrations/google/connect/`

Returns `{"authorization_url": "https://accounts.google.com/..."}`. Open it
(a popup works well). The user's saved `google_email`, if any, is used as the
sign-in hint. Returns `503` when the integration is not configured.

### `GET /api/integrations/google/callback/`

Called by Google's redirect, with no JWT. The signed, 10-minute `state`
identifies the user. The browser is redirected to
`{FRONTEND_URL}{GOOGLE_FRONTEND_RETURN_PATH}?status=connected` or
`?status=error&message=...`. If `FRONTEND_URL` is not set a JSON body is
returned instead.

### `DELETE /api/integrations/google/disconnect/`

Revokes the token at Google and deletes the stored connection.

## Meeting endpoints

### Create: `POST /api/meetings/`

Send `"add_google_meet": true` with the usual body.

- Host not connected: `400` `{"detail": "...", "code": "google_not_connected"}`; nothing is saved.
- All-day meeting: `400`; nothing is saved.
- The meeting is saved first, then the Google event is created.
- If Google fails the meeting **is still saved** with `conference_status: "failed"`.

Response `201`:

```json
{
  "id": "...",
  "message": "Meeting created successfully.",
  "meet_link": "https://meet.google.com/abc-defg-hij",
  "conference_status": "created",
  "conference_error": null
}
```

### Update: `PATCH /api/meetings/<id>/`

If the meeting has Meet and the title, description, location, start/end, host
or participants change, the Google event is patched and Google emails the
attendees the update. A Google failure never fails the update; the problem is
returned in `conference_error` (status stays `created`) and can be retried with
the conference endpoint below. A meeting that has Meet cannot be changed to
all-day.

### Delete: `DELETE /api/meetings/<id>/`

The Google event is cancelled and Google emails the cancellation.

### Add or retry: `POST /api/meetings/<id>/conference/`

No body. Adds Meet to a meeting that has none, retries a `failed` attempt, or
re-syncs a meeting whose last update failed to reach Google.

- `200` with the conference fields on success.
- `400` with `code: "google_not_connected"` when the host is not connected.
- `502` when Google failed again (state is saved as `failed`; retry later).

### Read: `GET /api/meetings/` and `GET /api/meetings/<id>/`

The list returns `meet_link` and `conference_status`. The detail also returns
`conference_provider` and `conference_error`.

`conference_status`: `none` | `created` | `failed`.

## Who is invited

The meeting's participants (users, leads, contacts), plus the host if the host
is not the calendar owner. The calendar owner is never invited as an attendee
(they are the organizer). Duplicate, blank and malformed emails are skipped.
Users are invited at their `google_email` when set, otherwise their `email`.
"Related To" records are not invited.

## Limitations

- All-day meetings cannot have Meet.
- While the Google app is in *Testing* mode, refresh tokens expire after 7
  days; the user sees `revoked` and must reconnect.
- If the host of a meeting is changed, the event stays on the original
  host's calendar and is updated through that connection.
- Meetings that are auto-deleted because their Related To lead/contact was
  deleted do not cancel their Google event.
- Reminders and the timeline do not include the Meet link.
