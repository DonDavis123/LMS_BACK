# Password reset email delivery

## Problem
Render's free web services block outbound SMTP ports 25, 465 and 587, so the
Django SMTP backend cannot connect there.

## Solution
The reset link is delivered with a plain HTTP POST (port 80/443), which is not
blocked. No third-party email SDK or vendor-specific API is used.

- `EmailService` (application interface) — unchanged.
- `ForgotPasswordUseCase`, `ResetPasswordUseCase` — unchanged.
- `infrastructure/email/http_email_service.py` — new `HttpEmailService`.
- `infrastructure/email/django_email_service.py` — SMTP, kept for local dev.
- `infrastructure/email/reset_link.py` — shared link builder (unchanged).
- `infrastructure/email/brevo_email_service.py` — **deleted**.
- `authentication_dependencies.py` — selects the adapter from `EMAIL_PROVIDER`.

## HTTP contract
```
POST {EMAIL_HTTP_ENDPOINT}
Content-Type: application/json
Authorization: Bearer {EMAIL_HTTP_TOKEN}     # only when set

{
  "to": "user@example.com",
  "subject": "Reset your Lead Management System password",
  "text": "...",
  "html": "...",
  "reset_link": "https://<frontend>/reset-password?token=..."
}
```
Any 2xx response counts as success; anything else is logged and raised
(`ForgotPasswordView` still returns the generic response).

## Environment variables
| Variable | Local | Render |
|---|---|---|
| `EMAIL_PROVIDER` | `smtp` (default) | `http` |
| `EMAIL_HTTP_ENDPOINT` | – | URL that receives the POST |
| `EMAIL_HTTP_TOKEN` | – | optional bearer token |
| `FRONTEND_URL` | `http://localhost:3000` | `https://<vercel-domain>` (no trailing slash) |
| `EMAIL_TIMEOUT` | optional | optional |
| `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS` | SMTP only | not needed |

`BREVO_API_KEY` is no longer used and can be removed from the environment.
