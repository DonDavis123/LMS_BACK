# Password reset email delivery

## Problem
Render's free web services block outbound SMTP ports 25, 465 and 587, so the
Django SMTP backend (Gmail on 587) cannot connect there.

## Solution
The backend POSTs the reset link to an HTTP endpoint (port 443, not blocked).
For `leadpulse123@gmail.com` that endpoint is a Google Apps Script web app
(`docs/google_apps_script_mailer.gs`) which sends the mail with `GmailApp`.

- `EmailService`, use cases — unchanged.
- `infrastructure/email/http_email_service.py` — `HttpEmailService`; also
  raises when the relay answers `{"ok": false}` (Apps Script returns HTTP 200
  even when sending fails).
- `infrastructure/email/django_email_service.py` — SMTP, local dev only.
- `ForgotPasswordView` / `ResetPasswordView` — `authentication_classes = []`
  so a stale Bearer token cannot cause a 401 on these public endpoints.

## Setup (Gmail via Apps Script)
1. Sign in as leadpulse123@gmail.com → https://script.google.com → New project.
2. Paste `docs/google_apps_script_mailer.gs`.
3. Project Settings → Script properties → add `MAIL_SECRET` = a long random string.
4. Run `authorizeOnce` in the editor and accept the Gmail permission.
5. Deploy → New deployment → type **Web app** → Execute as **Me** →
   Who has access **Anyone** → Deploy. Copy the URL ending in `/exec`.
   After any later script edit, use Deploy → Manage deployments → Edit →
   New version, otherwise the live URL keeps running the old code.

## Environment variables (Render)
| Variable | Value |
|---|---|
| `EMAIL_PROVIDER` | `http` |
| `EMAIL_HTTP_ENDPOINT` | `https://script.google.com/macros/s/<id>/exec?key=<MAIL_SECRET>` |
| `EMAIL_HTTP_TOKEN` | leave unset (Apps Script cannot read headers) |
| `EMAIL_TIMEOUT` | `20` (Apps Script cold starts take several seconds) |
| `FRONTEND_URL` | `https://lms-front-delta.vercel.app` |

Remove `BREVO_API_KEY`. `EMAIL_HOST*`, `EMAIL_PORT`, `EMAIL_USE_TLS`,
`DEFAULT_FROM_EMAIL` are only used by the SMTP provider (local dev).

## Limits
A consumer Gmail account can send about 100 Apps Script emails per day.

## Troubleshooting
Render logs: "Password reset email could not be sent." followed by either the
HTTP status/body, or "Mail endpoint reported a failure: <reason>".
- `unauthorized` → `?key=` does not match `MAIL_SECRET`.
- Redirect to a Google sign-in page / HTML body → web app access is not "Anyone".
