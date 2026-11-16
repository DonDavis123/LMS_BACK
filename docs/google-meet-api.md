# Google Meet for meetings

Meetings can get a Google Meet link, and everyone on the meeting is emailed a
Google Calendar invite. Google sends the invite, every later update and the
cancellation, from the **host's own Gmail** (`sendUpdates=all`).

Email is **independent of Meet**. The meeting has a `send_email_notifications`
option (see "Email notifications" below); with it on, people are emailed
whether or not Google Meet is added.

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

Send `"add_google_meet": true` with the usual body. Send
`"send_email_notifications": true` to email everyone (with or without Meet);
when omitted it follows `add_google_meet`.

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
  "conference_error": null,
  "send_email_notifications": true,
  "email_skipped": [
    { "name": "Jo Smith", "type": "CONTACT", "role": "participant", "reason": "no_email" }
  ]
}
```

`email_skipped` lists people who should have been emailed but have no usable
address (`reason`: `no_email` or `invalid_email`; `role`: `host`,
`participant` or `related`). It is also returned by `PATCH`.

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
`conference_provider`, `conference_error`, `send_email_notifications`, and the
`email` of every participant and related record.

`conference_status`: `none` | `created` | `failed`.

## Email notifications

`send_email_notifications` (create and `PATCH`) switches emails on for a
meeting. It does not need Google Meet.

| Situation | Invite / update / cancellation | Reminder before the meeting |
| --- | --- | --- |
| Email on, host connected to Google (timed meeting) | Google, through a calendar event (with a Meet link only if requested) | CRM email to everyone except the host (Google reminds the host) |
| Email on, host not connected, all-day meeting, or Google failed | CRM email (same mail setup as the reminder) | CRM email to everyone including the host |
| Email off | none | none |

Every email shows the meeting **title** and **description**, plus when, host,
location and the Meet link if there is one.

Meetings that had a Meet link before this option existed were switched on by
migration `0009`. Adding Meet later with `POST /conference/` switches email on.
Switching email on later sends everyone the invite they never got.

### Who is emailed

The host, every participant (users, leads, contacts) **and every "Related To"
lead/contact**. Duplicates are sent once. Users are emailed at their
`google_email` when set, otherwise their `email`. People without a valid
address are not emailed and come back in `email_skipped` (also logged on
reminders). The person who scheduled or edited the meeting does not get an
invite/update email for their own action.

### Google Calendar reminders

Each Google event sets popup + email reminders on the organizer's calendar at
the meeting's reminder time (default 15 minutes before). Google applies an
attendee's own default reminders to their copy of the event, so the CRM
reminder email below is what guarantees everyone is reminded.

## Limitations

- All-day meetings cannot have Meet.
- While the Google app is in *Testing* mode, refresh tokens expire after 7
  days; the user sees `revoked` and must reconnect.
- If the host of a meeting is changed, the event stays on the original
  host's calendar and is updated through that connection.
- Meetings that are auto-deleted because their Related To lead/contact was
  deleted do not cancel their Google event.
- Reminders and the timeline do not include the Meet link.
- Contacts' `email_opt_out` is not checked: meeting emails are transactional.

## Reminder emails

Runs inside the existing notification cron (`POST /api/internal/notifications/process/`
or `manage.py process_notifications`). **The cron must run about every minute.**

- Covers every meeting with `send_email_notifications` on, with or without Meet.
- Sent at the meeting's `reminder_at` if one is set, otherwise 15 minutes before `start_at`.
- Sent once per reminder time. Rescheduling the meeting re-arms it.
- A meeting created inside the reminder window gets no reminder (the invite just went out).
- If the mail relay is down the send is retried on the next cron run until the meeting ends.
- Uses the same mail setup as password reset (`EMAIL_PROVIDER` = `http` or `smtp`),
  sent from `DEFAULT_FROM_EMAIL`, one email per recipient.
- The cron response includes `meeting_reminder_emails_sent`.
