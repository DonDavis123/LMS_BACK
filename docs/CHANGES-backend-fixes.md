# Backend fixes (companies / platform admin)

## Behaviour changes
- **Company update (PATCH /api/platform/companies/{id}/)**: only fields whose
  value really changes are written and audited (`metadata.changed_fields`).
  Saving an unchanged form returns the company and writes no audit entry.
  The row is locked while updating so concurrent edits cannot overwrite each other.
- **Platform audit log**: a row with an action this build does not know is
  returned with its raw action instead of failing the whole list.
- **Errors**: any unexpected exception in an API view now answers
  `500 {"detail": "Something went wrong on the server. Please try again."}`
  (JSON, logged with traceback) instead of Django's HTML 500 page.
- **Notification cron** (`POST /api/internal/notifications/process/`): if any
  company fails, the response is now `500` (other companies are still
  processed) so the scheduler can alert. Previously it always returned 200.
- **Performance**: the company-suspension check runs once per request, not twice.

## Settings (optional environment variables)
- `DJANGO_EXTRA_ALLOWED_HOSTS` - comma-separated extra hosts (e.g. `.ngrok-free.dev`)
- `CORS_EXTRA_ALLOWED_ORIGINS` - comma-separated extra frontend origins
  (also added to CSRF trusted origins)

## Tests
The multi-tenant change left ~75 tests failing (repositories now need
`company_id`; test records were created without a company). They are updated;
the full suite (641 tests) passes on PostgreSQL. New tests:
`companies/test_platform_hardening.py`.
