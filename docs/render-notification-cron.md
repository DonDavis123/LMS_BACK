# Render production setup for notification processing

The backend already exposes a machine-to-machine endpoint:

```text
POST /api/internal/notifications/process/
```

It is intentionally separate from normal JWT-authenticated application APIs.

## 1. Set production environment variables

In the Render Dashboard, open the backend Web Service -> **Environment** and add:

```text
DJANGO_DEBUG=False
DJANGO_SECRET_KEY=<long-random-django-secret>
NOTIFICATION_CRON_SECRET=<long-random-cron-secret>
```

Also configure the database, email, frontend URL, and other variables required by `config/settings.py`.

Do **not** put real secrets in `render.yaml`, Git, Postman collections, or documentation.

Render supports adding environment variables from the dashboard and can generate secret values for Blueprint-managed services. See:
- https://render.com/docs/configure-environment-variables

## 2. Verify the deployment

After deployment, do not use a browser to trigger the endpoint. It is POST-only.

Test the endpoint from PowerShell:

```powershell
$headers = @{
  "X-Cron-Secret" = "<same-value-as-NOTIFICATION_CRON_SECRET>"
}

Invoke-RestMethod `
  -Method Post `
  -Uri "https://<your-backend>.onrender.com/api/internal/notifications/process/" `
  -Headers $headers
```

Expected successful response:

```json
{
  "status": "processed",
  "reminders_processed": 0,
  "task_notifications_created": 0,
  "meeting_notifications_created": 0,
  "duplicates_skipped": 0,
  "expired_notifications_deleted": 0,
  "failures": 0
}
```

A missing or incorrect secret returns `401`.

## 3. What the endpoint actually does

The HTTP endpoint is only an adapter. It calls the existing:

```text
ProcessNotificationsUseCase
```

The application layer remains responsible for:

- due reminders
- task due-today / due-tomorrow notifications
- meeting today / tomorrow notifications
- duplicate protection
- expired notification cleanup

This keeps the external scheduler out of the domain/application architecture.

## 4. Recommended schedule

For reminders that should appear close to their scheduled time, configure the external scheduler for **every minute**.

The processing use case is designed to be safe when called repeatedly: source-based duplicate checks prevent the same notification from being created again.

cron-job.org supports schedules as often as once per minute and supports custom HTTP headers and POST requests:
https://cron-job.org/en/

## 5. Render's native Cron Jobs

Render also supports native Cron Job services, but those are a different deployment model and are billed according to the service's active runtime. If you use cron-job.org, you do not need a second Render cron service.

Render documentation:
https://render.com/docs/cronjobs

## Security model

The endpoint:

- requires `POST`
- requires `X-Cron-Secret`
- uses constant-time `hmac.compare_digest`
- does not accept JWT as a substitute
- fails closed when `NOTIFICATION_CRON_SECRET` is missing
- returns generic errors instead of exception details
- does not put the secret in the URL
- sends `Cache-Control: no-store`

### Important limitation

This is a shared-secret endpoint. If the secret is leaked, someone could trigger processing. Keep it out of source control and rotate it if exposure is suspected.

Do not add the endpoint to the frontend UI or expose the secret to browser JavaScript.
