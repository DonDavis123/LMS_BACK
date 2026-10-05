# Password reset email delivery

## Problem
Password-reset emails worked locally but not on Render. Render's free web
services block outbound SMTP ports 25, 465 and 587 (since 26 Sept 2025), so
the Django SMTP backend can never connect there. Paid instances open 465/587;
port 25 stays blocked everywhere.

## Solution
Email is sent through an HTTPS API (port 443), which is not blocked.

- `EmailService` (application interface) is unchanged.
- `infrastructure/email/brevo_email_service.py` – new implementation using
  Brevo's HTTPS API (standard library only, no new dependency).
- `infrastructure/email/django_email_service.py` – SMTP implementation, kept
  for local development.
- `infrastructure/email/reset_link.py` – shared reset-link builder; strips a
  trailing slash from `FRONTEND_URL` and fails loudly when it is missing.
- `presentation/api/dependencies/authentication_dependencies.py` – chooses the
  implementation from `EMAIL_PROVIDER`.
- `ForgotPasswordView` – logs delivery failures but always returns the same
  generic response (no account enumeration).
- `EMAIL_TIMEOUT` (default 10s) – a blocked/slow mail server fails fast
  instead of hanging the gunicorn worker.

## Environment variables
| Variable | Local | Render |
|---|---|---|
| `EMAIL_PROVIDER` | `smtp` (default) | `brevo` |
| `BREVO_API_KEY` | – | Brevo API key |
| `DEFAULT_FROM_EMAIL` | any | `Name <sender verified in Brevo>` |
| `FRONTEND_URL` | `http://localhost:3000` | `https://<vercel-domain>` (no trailing slash) |
| `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS` | SMTP only | not needed |
| `EMAIL_TIMEOUT` | optional | optional |

Also make sure the Vercel domain is listed in `CORS_ALLOWED_ORIGINS`.

## Troubleshooting
Check the Render logs for "Password reset email could not be sent." — the
traceback (or Brevo's rejection reason, e.g. unverified sender / bad key)
follows it.
