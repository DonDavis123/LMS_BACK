# Notification Cron Endpoint

The notification scheduler can trigger the existing notification-processing use case over HTTPS.

## Endpoint

```text
POST /api/internal/notifications/process/
```

The endpoint is intended for machine-to-machine calls from an external scheduler. It is not a normal application-user API.

## Authentication

Send the shared secret in:

```text
X-Cron-Secret: <secret>
```

The server reads the expected value from:

```env
NOTIFICATION_CRON_SECRET=<long-random-secret>
```

Never put the secret in a URL, commit it to source control, or log it.

## Example cron-job.org configuration

```text
Method: POST
URL: https://<backend-domain>/api/internal/notifications/process/
Header:
    X-Cron-Secret: <secret>
```

Use HTTPS in production. A schedule of approximately once per minute is appropriate when timely reminder delivery is required.

## Response

A successful request returns HTTP 200 with the real processing counts from `ProcessNotificationsUseCase`, for example:

```json
{
  "status": "processed",
  "reminders_processed": 2,
  "reminders_deleted": 2,
  "task_notifications_created": 1,
  "meeting_notifications_created": 0,
  "duplicates_skipped": 1,
  "calls_marked_missed": 0,
  "expired_notifications_deleted": 0,
  "failures": 0
}
```

If processing fails unexpectedly, the endpoint returns HTTP 500 with a generic error message while the server logs the exception.

## Overdue planned calls

Each run also marks every **Planned** call whose start time is more than one hour in the past as **Missed**
(`calls_marked_missed` in the response, `Planned calls marked missed` in `manage.py process_notifications`).
The change is written to the call's timeline like a manual edit, and a Missed call stays editable, so the owner
can still log it as Completed later. Calls that were logged or edited while the job ran are left untouched.

## Architecture

The endpoint is only an HTTP adapter:

```text
External Scheduler
       |
       | HTTPS POST + X-Cron-Secret
       v
NotificationCronProcessView
       |
       v
ProcessNotificationsUseCase
       |
       +--> due reminders (one-time; consumed after successful processing)
       +--> task notifications
       +--> meeting notifications
       +--> overdue planned calls -> Missed (1 hour grace, via MarkMissedCallsUseCase)
       +--> duplicate protection
       +--> expired notification cleanup
       |
       v
Existing repositories / PostgreSQL
```

The existing management command continues to use the same application use case.

## Security notes

- The cron secret is mandatory.
- Missing or incorrect secrets return HTTP 401.
- JWT authentication alone does not grant access.
- GET does not trigger processing.
- The secret is compared using `hmac.compare_digest`.
- Secrets and request headers are not logged.
- Internal exception details are not returned to the caller.
