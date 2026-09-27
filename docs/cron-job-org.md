# cron-job.org configuration

This file is a configuration reference. It intentionally contains a placeholder instead of the real secret.

## Job settings

```text
Title:
LMS notification processor

URL:
https://<your-backend-domain>/api/internal/notifications/process/

Method:
POST

Schedule:
Every minute

Request body:
(empty)
```

## Custom header

Add exactly one custom header:

```text
X-Cron-Secret: <same-value-as-NOTIFICATION_CRON_SECRET-on-Render>
```

Do not put the secret in the URL or query string.

cron-job.org supports custom headers and POST requests. It also provides a test-run feature and execution history.

Official documentation:
https://cron-job.org/en/faq/
https://docs.beta.cron-job.org/creating-cron-jobs.html

## First test

1. Deploy the backend to Render.
2. Confirm `NOTIFICATION_CRON_SECRET` exists in the Render backend service.
3. Create the cron job with the URL, POST method, and header above.
4. Use cron-job.org's **Test run**.
5. Expect HTTP `200`.
6. Open the cron-job.org execution details and verify the response body contains `"status": "processed"`.

## Failure meanings

```text
401 -> secret missing or incorrect
405 -> request method is not POST
500 -> notification processing failed; inspect Render logs
200 -> scheduler reached the endpoint and the processing use case completed
```

A `200` does not necessarily mean a notification was created. The response counters tell you what happened during that run.
