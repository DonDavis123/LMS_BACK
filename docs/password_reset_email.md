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
- `infrastructure/email/relay_diagnostics.py` — turns a failed relay call
  into a readable log line (status, host, page title, likely fix) and strips
  the `?key=` secret from anything logged.
- `infrastructure/email/django_email_service.py` — SMTP, local dev only.
- `ForgotPasswordView` / `ResetPasswordView` — `authentication_classes = []`
  so a stale Bearer token cannot cause a 401 on these public endpoints.

## Setup (Gmail via Apps Script)
1. Sign in as leadpulse123@gmail.com → https://script.google.com → New project.
2. Paste `docs/google_apps_script_mailer.gs`.
3. Project Settings → Script properties → add `MAIL_SECRET` = a long random string.
4. Run `authorizeOnce` in the editor and accept the Gmail permission.
5. Project Settings → tick "Show appsscript.json manifest file in editor",
   then replace its content with `docs/appsscript.json`. This pins
   `executeAs: USER_DEPLOYING` and `access: ANYONE_ANONYMOUS`, which is what
   a server-to-server call needs.
6. Deploy → New deployment → type **Web app** → Execute as **Me** →
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

## Fixing `HTTP 401 ... HTML page` (Google rejects the request)
The 401 is produced by Google *before* your script runs, so no backend
change can cure it; the web app deployment is not public. Fix:
1. script.google.com → open the mailer project, signed in as the Gmail owner.
2. Deploy → Manage deployments → pencil icon on the active deployment.
3. Execute as **Me**, Who has access **Anyone** (not "Anyone with Google
   account"), Version **New version** → Deploy.
4. Open the `/exec` URL (without `?key=`) in a private window. It must show
   `{"ok":true,"service":"leadpulse-mailer"}`. If it asks you to sign in,
   it is still not public (a Google Workspace admin policy can also forbid
   "Anyone"; a plain @gmail.com account has no such restriction).
5. If you created a new deployment, its URL is new: update
   `EMAIL_HTTP_ENDPOINT` on Render and redeploy.

## Troubleshooting
Render logs: "Password reset email could not be sent." followed by either the
HTTP status/body, or "Mail endpoint reported a failure: <reason>".
- `unauthorized` → `?key=` does not match `MAIL_SECRET`.
- "Mail endpoint returned a web page instead of a result" or
  "HTTP 401 ... HTML page" → web app access is not "Anyone" (see above).
