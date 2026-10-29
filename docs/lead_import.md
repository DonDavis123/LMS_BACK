# Lead import

Admins and superadmins can import leads from a CSV or .xlsx file. Everything is
limited to the caller's own company.

## The 8 steps

1. **Upload** the file. The server reads it and saves a draft import.
2. **Map columns**: say which file column goes to which lead field.
3. **Mapping preview**: a quick look at a few rows with the mapping applied.
4. **Choose the owner option** (see below).
5. **Full check** (validate): every row is checked; errors and duplicates are
   counted and shown. Rows can be excluded here.
6. **Choose the duplicate action** once for the whole file.
7. **Import**: the rows are added in batches of about 500, with a progress bar.
8. **Finish**: a notification, a detailed report, and downloadable files of the
   rows that were not added.

## Endpoints

All under `/api/leads/import/`, all need a logged-in admin or superadmin
except `maintenance/`.

| Method and path | What it does |
| --- | --- |
| `GET template/` | Download a sample file. |
| `POST upload/` | Upload a file; returns the draft job, headers and a suggested mapping. |
| `POST <job_id>/mapping-preview/` | Preview a few rows with the given mapping and options. |
| `POST <job_id>/validate/` | Check every row; returns counts, problems and duplicates. |
| `GET <job_id>/rows/` | Page through the checked rows. |
| `PATCH <job_id>/exclusions/` | Exclude rows (by number or rule) from the import. |
| `POST <job_id>/start/` | Save mapping and options and start the import. |
| `POST <job_id>/process/` | Process the next batch; returns progress and `next_action`. |
| `GET <job_id>/progress/` | Current progress (no work is done). |
| `POST <job_id>/cancel/` | Stop after the current batch; leads already added are kept. |
| `GET <job_id>/report/` | Detailed report. |
| `GET <job_id>/rejected-file/` | Download the rows that were not added. |
| `GET <job_id>/results-file/` | Download every row with its result. |
| `GET <job_id>/undo-preview/` | Show what an undo would remove or leave. |
| `POST <job_id>/undo/` | Undo the import. |
| `GET history/` | Past imports of the company. |
| `DELETE <job_id>/` | Discard a draft. |
| `GET/POST maintenance/` | Cron only: secret header, no login (see below). |

## Owner options

- **Me** (default): the user who runs the import owns every lead.
- **From file**: the file's owner column is matched to a user (by a value
  mapping you give, then by email, then by exact full name). A blank or unknown
  value takes the fallback owner (one owner, or several in rotation).
- **Selected**: one owner, or a group in rotation, for every lead. The file's
  owner column is ignored.

An owner must be an active admin or superadmin of the company.

## Duplicate rules

- A row **with an email** is matched on email only.
- A row **without an email** is matched on phone/mobile only (the last 10
  digits; fewer than 7 digits is too short to match).
- Name and company are never used.
- Rows that repeat inside the file are detected too.
- The action is chosen once for the file: **skip**, **update** the existing
  lead, or **create anyway**.
- A lead that is already converted is never updated; the row is skipped and
  reported.

## Convert on import

A row marked as converted in the file is created as a lead and then converted
into an Account and a Contact, using the same code as the Convert Lead button.
Only new rows are converted (an existing lead is never converted by an
import). Existing accounts and contacts are reused or newly created according
to the account and contact matching choices. A row that fails is rolled back as
a whole (lead, account and contact) and reported; other rows carry on.

## Limits

- File size: 10 MB (`LEAD_IMPORT_MAX_BYTES`).
- Rows: 10,000 (`LEAD_IMPORT_MAX_ROWS`).
- Batch size: about 500 rows (`LEAD_IMPORT_BATCH_SIZE`).
- One running import per company at a time.

## Where data is stored, and the 30-day purge

An import is a saved job in Postgres (`lead_import_jobs`). It holds the mapping,
options, counters, problems and the stored file rows (`rows`).

- Drafts that were never started are deleted after 24 hours.
- The stored rows of a finished import are removed after 30 days
  (`LEAD_IMPORT_RETENTION_DAYS`). History, counts, problem summaries, the
  created/converted id lists and the update snapshots stay, so the history page
  and undo keep working. After the purge the rejected/results files can no
  longer be built from the rows.

## Maintenance endpoint and cron-job.org

`/api/leads/import/maintenance/` is called by a scheduler. It is not protected
by a login, only by the secret header `X-Import-Secret`. If the secret is not
configured, or the header is missing or wrong, the answer is an empty 404.
One call, in about 20 seconds at most:

1. resumes up to 3 stalled imports (running, no activity for 2 minutes);
2. deletes drafts older than 24 hours;
3. clears stored rows of finished imports older than the retention period;
4. marks imports stuck in "processing" for over 24 hours after 3+ failed
   batches as failed.

It answers `{resumed, drafts_deleted, rows_purged, marked_failed, errors, took_ms}`.
A step that fails is reported in `errors` and never blocks the others. Running
it twice at once is safe.

Set up (cron-job.org):

1. On Render, add `LEAD_IMPORT_CRON_SECRET` with a long random value, redeploy.
2. In cron-job.org create a job with URL
   `https://<your-render-host>/api/leads/import/maintenance/`.
3. Method **POST**.
4. Add the header `X-Import-Secret` with the same value as in step 1.
5. Schedule: every 5 minutes. Use "Test run" and check for a 200 answer.

Render free instances sleep, so the first call after a quiet period can take
about 30 seconds. A second cron job on the same URL is not needed.

## Undo

Undo removes what the import created and restores what it updated, but only
where nothing was changed afterwards. Nothing is deleted for good (records are
marked deleted). Use `undo-preview` first: it lists what will be removed and
what will be left alone, with reasons. Anything left alone is reported and the
import becomes "partly undone"; a later attempt checks the leftovers again.

## Frontend contract

```
upload -> mapping-preview -> validate -> start
loop:
    POST /import/<job_id>/process/   body (optional): {"processed_rows": <last seen>}
    show percent / counts from the answer
    stop when next_action is "done" or "failed"
GET /import/<job_id>/report/
```

`next_action` is `call_process_again`, `done` or `failed`. Sending the last
seen `processed_rows` makes a repeated request harmless. If the browser is
closed, the maintenance endpoint finishes the import; on return, call
`progress/` and continue the loop if needed.

## Moving to a real server later

1. Install Celery and Redis and configure a Celery app.
2. Create a task that calls `process_next_batch(job_id)` until done:

```python
from celery import shared_task
from src.modules.leads.application.services.lead_import_processor import (
    NEXT_PROCESS_AGAIN, process_next_batch,
)

@shared_task
def run_lead_import(job_id):
    while process_next_batch(job_id).next_action == NEXT_PROCESS_AGAIN:
        pass
```

3. Call `run_lead_import.delay(job_id)` from the start endpoint instead of
   processing inline.
4. Keep the maintenance endpoint as a safety net.
