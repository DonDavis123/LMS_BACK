LeadPulse CRM Backend

Django REST API for LeadPulse (LMS), a multi-tenant CRM for lead management, sales pipelines, calls, meetings and tasks.

What is this?

LeadPulse (LMS) is a CRM in the spirit of Zoho / HubSpot: leads flow in from forms, imports and manual entry, get worked through calls, meetings, tasks and reminders, and are converted into Accounts, Contacts and Deals that move across a Kanban pipeline until they are won or lost.

This repository is the backend: a Django 6 + Django REST Framework JSON API, backed by PostgreSQL, designed so that many companies (tenants) share one deployment with hard data isolation, and so that the business logic stays independent of the framework.

It is consumed by the Next.js frontend (LMS_FRONT), which talks to it through NEXT_PUBLIC_API_URL (e.g. http://127.0.0.1:8000/api).

At a glance
	
Feature modules	21 bounded modules + 1 shared kernel
HTTP routes	120+ under /api/
Database migrations	94
Automated tests	1,700+ test cases (unit, integration, tenant-isolation, query-count guards)
Python code	~1,300 files, ~93k lines (tests included)
AI features	Call transcription and summaries, lead / contact / account briefings, "Plan my day" (Google Gemini)
Integrations	Google Calendar / Meet (OAuth), Gmail compose helpers, Supabase Storage (S3-compatible), Redis, external cron
Table of contents
Feature highlights
Tech stack
Architecture
Multi-tenancy and security
Domain modules
Feature deep dives
API conventions
Endpoint map
Quick start
First-run walkthrough
Configuration
Performance and caching
Background work and schedulers
Management commands
Testing
Deployment
Project structure
Documentation index
Extending the codebase
Troubleshooting
License
Feature highlights

Sales core

Leads with search, JSON filters, sorting, pagination, duplicate protection and one-click conversion into Account + Contact (+ optional Deal).
Accounts, Contacts, Deals, Tasks, Calls, Meetings, Reminders, all tenant-scoped and soft-deleted.
Deals pipeline: Kanban board, revenue forecast, stage rules with default win probabilities, lost-reason enforcement.
Unified timeline per record (leads, contacts, accounts, tasks, meetings, calls, deals) recorded automatically from use cases.
Unified calendar feed combining tasks, calls, meetings and reminders (personal or team scope).
Company-customisable picklists: every dropdown (lead source, status, industry, rating, ...) is editable per company, with colours, ordering and a protected "None" option.

Data in and out

8-step lead import from CSV / XLSX: column mapping, full validation, duplicate policy, owner assignment (me / from file / rotation), batch processing with progress, downloadable reject files, and undo.
Public lead-capture form per company: unguessable link / QR, honeypot, throttling, daily cap, round-robin owner assignment.
CSV / XLSX export of any list with the same filters as the screen, spreadsheet-formula injection neutralised.
Bulk mail helper: resolves a selection into deduplicated Bcc batches for Gmail compose, and logs "email opened in Gmail" on the record timeline.

Intelligence (Google Gemini)

Call recordings are stored privately and transcribed with speaker labels, summary, key points and action items in the background.
Lead / contact / account summaries built from each record's whole history and stored until refreshed.
Plan my day: ranks the user's open tasks with today's meetings in mind and explains the order.

Collaboration and operations

Google Meet links and Google Calendar invites, sent from the host's own Gmail account.
Notification engine: due reminders, task due today/tomorrow, meeting today/tomorrow, overdue planned calls auto-marked Missed, import finished/undone alerts.
User management with roles, block / unblock, audit trail, password reset by admins, and safe retirement (records transferred to a replacement owner).

Platform administration (SaaS operator)

Create companies with their first SUPERADMIN in one transaction, suspend / reactivate (takes effect on the next request), manage company users, view a platform audit log and an overview dashboard.
Tech stack
Layer	Technology
Language / framework	Python 3.12+, Django 6.1, Django REST Framework 3.18
Auth	djangorestframework-simplejwt 5.5 (access token in JSON, refresh token in an HttpOnly cookie, rotation + blacklist)
Database	PostgreSQL via psycopg 3 (uses pg_trgm, partial/composite indexes, SELECT ... FOR UPDATE)
Cache / throttling	Redis through Django's built-in backend (falls back to in-process LocMemCache when REDIS_URL is unset)
File storage	Private Supabase Storage bucket through django-storages[s3] + boto3, or local MEDIA_ROOT in development
AI	Google Gemini REST API (plain requests, no SDK), default model gemini-2.5-flash
Google OAuth	Hand-rolled OAuth 2.0 client; refresh tokens encrypted at rest with Fernet (cryptography)
Spreadsheets	openpyxl for XLSX import / export
Serving	gunicorn (WSGI), collectstatic build step
CORS	django-cors-headers with credentials, explicit methods, and a preview-deployment regex
Architecture

LeadPulse follows Clean / Hexagonal Architecture, applied per module. The business rules never import Django or DRF; frameworks and vendors are plugged in at the edges.

The dependency rule: domain ← application ← (infrastructure, presentation). Use cases depend only on interfaces (application/interfaces); Django-specific classes live in infrastructure and are injected by the factories in presentation/api/dependencies.

Anatomy of a module

Every feature module has the same shape, so you can navigate any of them blind:

src/modules/<module>/
├── domain/                   # Pure Python: entities, enums, rules (no Django, no DRF)
│   ├── entities/
│   └── enums/
├── application/              # What the module can DO
│   ├── use_cases/            #   one class per action: execute(...)
│   ├── dto/                  #   input / output data shapes
│   ├── services/             #   reusable application logic
│   └── interfaces/           #   ports: repositories, mailers, generators, ...
├── infrastructure/           # How it is done with real tools
│   └── persistence/          #   Django models + repository implementations
├── presentation/api/         # HTTP
│   ├── views/                #   thin APIViews
│   ├── serializers/          #   request / response validation
│   ├── dependencies/         #   factories that build use cases for a TenantContext
│   └── urls.py
├── migrations/
└── test_*.py                 # tests sit next to the code they cover
Anatomy of a request
CachedJWTAuthentication reads the bearer token and loads the user (from cache first, then the database).
The view checks IsAuthenticated, IsCompanyUser and any role permission.
get_tenant_context(request) builds a TenantContext (company id, user id, role) from request.user.
A dependency factory builds the use case with repositories scoped to that company_id.
The use case runs and either returns a result or raises ValueError for a business-rule violation.
The view serialises the result, or returns 400 {"detail": ...}.

A real view is intentionally boring, because the interesting work is in the use case:

python
class DeleteLeadView(APIView):
    permission_classes = [IsAuthenticated, IsCompanyUser]

    def delete(self, request, lead_id):
        use_case = get_delete_lead_use_case(get_tenant_context(request))
        try:
            use_case.execute(UUID(str(lead_id)))
        except ValueError as error:
            return Response({"detail": str(error)}, status=400)
        return Response({"message": "Lead deleted successfully."}, status=200)
Design decisions worth knowing
Decision	Why
TenantContext is built from request.user, never from the request body	A client can never choose which company it acts for.
Repositories take company_id in their constructor	Every query is scoped by construction; forgetting a WHERE company_id is structurally hard.
Use cases raise ValueError for business-rule violations; views map them to 400 {"detail": ...}	One predictable error contract for the frontend.
TransactionManager is a port (DjangoTransactionManager implements it)	Use cases stay atomic without importing Django.
Timeline recording is a service (DefaultTimelineRecorder)	Every create / update / delete / stage change leaves an activity trail with no per-view boilerplate.
Soft delete everywhere (is_deleted; users use deleted_at)	Records are never lost; imports are undoable; history stays intact.
Per-company picklists seeded from enums	Code enums are only the starting point; each company edits its own copy.
Caches are optimisations, never dependencies	If Redis is down, the app reads the database.
Unexpected exceptions return JSON (500 {"detail": "Something went wrong..."})	The frontend always has a message to show instead of an HTML error page.
Multi-tenancy and security
Roles
Role	Belongs to a company?	What it can do
PLATFORM_SUPERADMIN	No	Operate the SaaS: companies, company users, platform audit log, overview. Cannot read any company data (403 "A company account is required.").
SUPERADMIN	Yes	Everything inside the company, plus manage users, configure picklists and the lead-capture form.
ADMIN	Yes	See and manage all leads, import / export, and every other company feature except user management, picklist editing and lead-capture settings.
SALES_MANAGER, SALES_EXECUTIVE	Yes	Defined in the role enum for future use; user management currently assigns only SUPERADMIN and ADMIN, and the lead list and import are limited to those two roles.

Role and active status are read per request (through a short-lived cache that is invalidated on every save), so a block, role change or deletion applies immediately, not when the 15-minute access token expires.

Isolation guarantees
Every tenant-owned table carries a company foreign key, and every list index starts with (company, is_deleted, ...).
A record that belongs to another company behaves exactly like a record that does not exist (404), so nothing about other tenants leaks.
Platform superadmins, inactive users and users without a company never obtain a TenantContext.
A suspended company is rejected with 403 on its next request (suspension state is cached per request and cleared immediately on change).
Dedicated tenant-isolation test suites exist for deals, users, lead conversion, and the tenancy permission layer.
python manage.py audit_tenant_data reports rows with a missing or inconsistent company and exits non-zero if it finds any, so it can run in CI or after a data migration.
Authentication flow
POST /api/auth/login/ with email and password returns {access_token} and sets the refresh_token HttpOnly cookie.
Every request sends Authorization: Bearer <access_token>. The access token lives 15 minutes.
POST /api/auth/refresh/ (cookie) returns a new access token and a rotated refresh cookie; the old refresh token is blacklisted.
POST /api/auth/logout/ revokes the refresh token and clears the cookie.
Access token: 15 minutes, sent as Authorization: Bearer .... Refresh token: 7 days, rotated on every use and blacklisted afterwards; it is never in JSON or readable by JavaScript.
Cookie flags are chosen per request: plain HTTP uses Secure=False; SameSite=Lax; HTTPS (including tunnels such as ngrok, via X-Forwarded-Proto) uses Secure=True; SameSite=None. The same code works locally and in production.
A password reset, block, role change or deletion revokes the user's refresh tokens.
Email matching is case-insensitive and unique across all companies (enforced by a lower-case unique index).
Password reset

Reset tokens are 32 random bytes, stored only as a SHA-256 hash, valid for 15 minutes, single use, and issuing a new one invalidates older unused ones. forgot-password never reveals whether an email exists. Mail is sent through SMTP (local) or an HTTPS relay (for hosts that block SMTP), see Configuration.

Hardening checklist (already implemented)
Constant-time (hmac.compare_digest) secret comparison on machine-to-machine endpoints; secrets never in URLs or logs; Cache-Control: no-store.
Public endpoints disable JWT authentication so a stale Authorization header cannot break them.
Only the public lead-capture endpoints are throttled, and the limits are global across workers when Redis is configured.
Google refresh tokens are Fernet-encrypted at rest; the OAuth state is signed and expires.
Call recordings are never served from a public URL: an authenticated, tenant-scoped endpoint streams them.
Exports neutralise cells starting with =, +, -, @.
Audit trails: user audit log (company level) and platform audit log (operator level); neither stores passwords or tokens.
CORS allows credentials only for an explicit origin list plus a regex scoped to this project's preview deployments, never all of *.vercel.app.
Domain modules
Module	Responsibility	Mounted at
authentication	Login, refresh, logout, forgot / reset password, cached JWT authentication, lead-view permission rules	/api/auth/
users	Company users, roles, block / unblock, retire with record transfer, audit log, own Google mail address, lead owners, assignable users	/api/users/..., /api/lead-owners/
companies	Tenants and the platform-operator console (create, update, suspend, activate, company users, audit log, overview)	/api/platform/...
leads	Lead CRUD, filters, conversion, bulk import engine, AI summary	/api/leads/
contacts	Contact CRUD, AI summary	/api/contacts/
accounts	Account CRUD, document links, AI summary	/api/accounts/
deals	Deal CRUD, stage moves, Kanban board, forecast	/api/deals/
tasks	Tasks linked to records, due-date and status tracking	/api/tasks/
calls	Call logging (manual or timer), outcomes, history, recordings, transcription	/api/calls/
meetings	Meetings with participants, Google Meet conference links and invites	/api/meetings/
reminders	One-time reminders consumed by the notification engine	/api/reminders/
notifications	In-app notifications and the processing engine run by the scheduler	/api/notifications/, /api/internal/notifications/process/
calendar	Unified events feed for tasks, calls, meetings and reminders	/api/calendar/
timeline	Per-record activity history	/api/timeline/
dashboard	Aggregated stats and the AI daily briefing	/api/dashboard/
picklists	Per-company customisable dropdown options	/api/picklists/
lead_capture	Shareable public lead form and its management	/api/lead-capture/, /api/public/lead-forms/
google_integration	Google OAuth connection (status, connect, callback, disconnect)	/api/integrations/google/
exports	CSV / XLSX export of lists	/api/exports/
mailing	Recipient resolution into Bcc batches	/api/mail/
email_activity	Timeline entry when an email is opened in Gmail	/api/email-activity/
shared	Kernel: TenantContext, permissions, list-query parsing, transaction port, duplicate guard, caches, exception handler, field validation	/api/validate/

The Django admin is available at /admin/.

Feature deep dives
Lead lifecycle

Leads come from the public lead form, CSV/XLSX import or manual entry. Converting a lead creates an Account and a Contact, and optionally a Deal.

Conversion runs in one transaction; conversion-check previews matches with existing accounts / contacts first. A converted lead is locked from further edits and from import updates.
Duplicate guard prevents the same email or phone from being used by two records in a company across leads, contacts and accounts. POST /api/validate/field/ lets forms check as you type.
Deals
Stage	Default probability
New	10%
Quotation Sent	40%
Negotiation	70%
Won	100%
Lost	0%

Stage rules are applied by the domain entity (Deal.move_to_stage), so they are identical for POST /{id}/move/, PATCH /{id}/ and POST /: open stages take the default probability unless one is sent; Won forces 100% and stamps closed_at; Lost forces 0% and requires a lost reason; reopening a closed deal clears both. Money is a decimal string ("100000.00"). Default probabilities live in one place (DEFAULT_PROBABILITY).

Lead import (8 steps)

upload → map columns → mapping preview → choose owner → full validation → choose duplicate action → import in batches → report

Owner options: Me, From file (matched by value-map, then email, then exact name, with fallback owners in rotation), or Selected (one owner or a rotating group). Owners must be active ADMIN / SUPERADMIN of the company.
Duplicates: matched by email, or by the last 10 digits of the phone when there is no email; also detected inside the file. One policy per file: skip, update, or create anyway.
Convert on import: rows flagged as converted become Account + Contact through the same code as the Convert button; a failing row is rolled back alone.
Limits: 10 MB, 10,000 rows, ~500-row batches, one running import per company.
Resilient: progress is polled with process/; if the browser closes, the scheduler endpoint resumes stalled imports.
Undo: removes what the import created and restores what it updated, only where nothing changed afterwards, and tells you what it left alone and why.
Retention: stored file rows are purged after 30 days; history, counts and undo data remain.
Public lead-capture form

One form per company, created with the company, blocked and unconfigured by default. A SUPERADMIN sets the lead source and either a single owner or a rotation; only then can it be unblocked. The public URL is {FRONTEND_URL}/lead/{token} (an unguessable secrets.token_urlsafe(24)); the frontend draws the QR code. Submissions are throttled, capped per day (HTTP 410 once reached), protected by a honeypot (fax_number), and de-duplicated by email: a returning visitor updates the existing lead and appends the new message instead of creating a copy, with an identical response so email existence is not revealed. Concurrent submissions rotate owners correctly because the form row is locked.

Calls, recordings and transcription

Flow: upload recording, store it privately, queue a background worker, Gemini returns transcript and summary, the client polls GET .../transcript/.

Calls have a type (Outbound / Inbound), status (Planned / Completed / Missed), an outcome (Connected, Not Attended, Busy, Voicemail, Wrong Number, Callback Requested) and an entry method (Manual / Timer). Recordings (default max 25 MB, 10 per call, optional global storage cap) are transcribed automatically; the transcript status moves NOT_REQUESTED → PENDING → PROCESSING → COMPLETED | FAILED. A failed transcription never fails the upload. The transcript keeps the spoken language; the summary language is configurable.

AI summaries and daily briefing
Lead / contact / account summary: GET returns the stored summary (free), POST regenerates it from the record's full timeline (one model request; the old summary is replaced only if the new one succeeds).
Plan my day (POST /api/dashboard/briefing/): ranks the caller's open tasks, factoring in meetings today, and explains each priority. Nothing is stored.
Without GEMINI_API_KEY these features are simply off (503); nothing else is affected.
Google Meet and Calendar

Each user connects their own Google account (OAuth, scope calendar.events). Meetings can get a Google Meet link and everyone on the meeting is emailed a Calendar invite, update and cancellation from the host's own Gmail (sendUpdates=all). Email notifications are independent of Meet. Refresh tokens are Fernet-encrypted.

Notifications

The scheduler calls one endpoint, which runs ProcessNotificationsUseCase: due reminders (one-shot), task due today / tomorrow, meeting today / tomorrow, overdue Planned calls (> 1 h) marked Missed (still editable), duplicate protection, and expired-notification cleanup. Import finished / undone events also notify the user.

Exports, mailing and email activity
GET /api/exports/<entity>/?format=csv|xlsx reuses the list use case, so filters, search and sorting match the screen; up to 10,000 rows; UTF-8 BOM for Excel; times in the project time zone.
POST /api/mail/recipients/resolve/ turns a selection (ids, or "everything matching the filters") into deduplicated Bcc batches of up to 50 addresses. The server sends no mail; the browser opens Gmail compose.
POST /api/email-activity/compose/ records EMAIL_COMPOSED ("Email opened in Gmail by ...") on the timeline. The wording is deliberately "opened", never "sent", because the server cannot know.
Platform administration

PLATFORM_SUPERADMINs create a company and its first SUPERADMIN atomically (the lead form is created in the same transaction), edit it (only really-changed fields are written and audited, rows are locked against concurrent edits), suspend / activate, manage a company's users, and browse the audit trail and an overview with growth, users-by-role and top companies. A suspended company can still be managed from here.

User retirement

Deleting a user is a guided flow: deletion-preview shows the impact, replacement-candidates lists who can take over, and DELETE transfers leads, contacts, accounts and hosted meetings to the replacement while permanently removing the user's own tasks, reminders and notifications. Timeline history is always kept. The user is soft-deleted and their sessions revoked.

API conventions
Topic	Convention
Base URL	http(s)://<host>/api/
Auth	Authorization: Bearer <access_token>; refresh via cookie
Format	JSON bodies (Content-Type: application/json); IDs are UUIDs
Timestamps	ISO-8601 with offset; storage is UTC; rendering uses APP_TIME_ZONE (default Asia/Kolkata)
Money	Decimal strings, e.g. "100000.00"
Pagination	?page=1&page_size=20 → {"results": [...], "pagination": {"page", "page_size", "total", "total_pages"}} (platform lists cap page_size at 50)
Search	?search=acme (backed by trigram indexes; 3+ characters use the index)
Sorting	?sort_by=created_at&sort_direction=asc (or desc)
Filtering	?filters=[{"field":"lead_status","operator":"equals","value":"Contacted"}], a JSON array. Operators depend on the field type: text (contains, equals, starts_with, ends_with, not_contains, not_equals), choice (equals, not_equals, in, not_in), dates (equals, before, after, between). Bad combinations return 400 with a precise message.
Business-rule errors	400 {"detail": "message"}
Validation errors	400 {"field": ["message"]} (DRF standard)
Auth errors	401 missing / invalid token, 403 wrong role, suspended company, or platform admin on company data
Not found	404, also for records that belong to another company
Unexpected errors	500 {"detail": "Something went wrong on the server. Please try again."} (logged with traceback)

Every field-level rule, status code and example response is documented in docs/.

Endpoint map
<details> <summary><b>Click to expand the full route table (120+ routes)</b></summary>

Unless noted, endpoints require a JWT of a company user (IsAuthenticated + IsCompanyUser).

Authentication, /api/auth/ (public)
Method	Path	Purpose
POST	login/	Email + password → access token + refresh cookie
POST	refresh/	Rotate refresh cookie, new access token
POST	logout/	Revoke refresh token, clear cookie
POST	forgot-password/	Send reset link (never reveals if the email exists)
POST	reset-password/	Set a new password with a valid token
Users, /api/
Method	Path	Who	Purpose
GET, POST	users/	SUPERADMIN	List / create users
GET	users/me/	any logged-in user	Current user, company, mail account
PATCH	users/me/google-email/	company user	Set / clear own Google mail
GET	users/assignable/	company user	Users selectable as owners
GET	users/audit-logs/	SUPERADMIN	User audit trail
GET, PATCH, DELETE	users/{id}/	SUPERADMIN	Profile / edit / retire
GET	users/{id}/deletion-preview/	SUPERADMIN	Impact of retiring
GET	users/{id}/replacement-candidates/	SUPERADMIN	Who can take over records
POST	users/{id}/reset-password/, block/, unblock/	SUPERADMIN	Account controls
GET	lead-owners/	company user	Eligible lead owners
Platform, /api/platform/ (PLATFORM_SUPERADMIN only)
Method	Path	Purpose
GET, POST	companies/	List / create company + first SUPERADMIN
GET, PATCH	companies/{id}/	Detail / update
POST	companies/{id}/suspend/, activate/	Change status
GET, POST	companies/{id}/users/	List / create company users
POST	companies/{id}/users/{uid}/reset-password/, block/, unblock/	User controls
GET	audit-logs/	Platform audit trail
GET	overview/	Platform dashboard data
Leads, /api/leads/
Method	Path	Purpose
GET	``	List (ADMIN / SUPERADMIN)
POST	create/	Create
GET	{id}/	Details
PATCH	{id}/update/	Update
DELETE	{id}/delete/	Soft delete (cascades to related tasks / calls)
GET	{id}/conversion-check/	Preview conversion matches
POST	{id}/convert/	Convert to Account + Contact (+ Deal)
GET, POST	{id}/summary/	Stored / regenerate AI summary
GET	import/template/	Sample file
POST	import/upload/	Upload file, get draft job
GET	import/history/	Past imports
POST	import/{job}/mapping-preview/, validate/, start/, process/, cancel/, undo/	Import steps
GET	import/{job}/rows/, file-rows/, progress/, report/, rejected-file/, results-file/, undo-preview/	Import reads and downloads
PATCH	import/{job}/exclusions/	Exclude rows
DELETE	import/{job}/	Discard a draft
GET, POST	import/maintenance/	Scheduler only (X-Import-Secret)
Contacts, /api/contacts/ · Accounts, /api/accounts/
Method	Path	Purpose
GET	``	List
POST	create/	Create
GET	{id}/	Details
PATCH (contacts) / PUT (accounts)	{id}/update/ (accounts: {id}/update)	Update
DELETE	{id}/delete/	Soft delete
GET, POST	{id}/summary/	Stored / regenerate AI summary
GET, POST	accounts/{id}/documents/	List / add document links
PUT, DELETE	accounts/{id}/documents/{doc}/	Edit / remove a document link
Deals, /api/deals/
Method	Path	Purpose
GET, POST	``	List / create
GET	board/	Kanban board
GET	forecast/	Revenue forecast
GET, PATCH, DELETE	{id}/	Detail / update / delete
POST	{id}/move/	Move stage
Tasks, Meetings, Reminders, Notifications
Method	Path	Purpose
GET, POST	/api/tasks/ · /api/meetings/ · /api/reminders/	List / create
GET, PATCH, DELETE	/api/tasks/{id}/ · /api/meetings/{id}/ · /api/reminders/{id}/	Detail / update / delete
POST	/api/meetings/{id}/conference/	Add or retry Google Meet
GET	/api/notifications/, unread/	List notifications
GET, PATCH, DELETE	/api/notifications/{id}/	Detail / update / delete
PATCH	/api/notifications/{id}/read/	Mark read
Calls, /api/calls/
Method	Path	Purpose
GET, POST	``	List / log a call
GET	records/	One row per lead / contact with call_count and latest_call (the Calls table)
GET, PATCH, DELETE	{id}/	Detail / update / delete
GET	{id}/history/	Call history
GET, POST	{id}/recordings/	List / upload recordings
DELETE	{id}/recordings/{rec}/	Delete a recording (and its transcript)
GET	{id}/recordings/{rec}/file/	Authenticated audio stream
GET, POST	{id}/recordings/{rec}/transcript/	Poll / start / retry / regenerate transcript
Everything else
Method	Path	Purpose
GET	/api/calendar/events/?start=&end=[&types=][&scope=team][&owner_id=]	Unified events (start / end are ISO-8601 with offset)
GET	/api/timeline/{leads|contacts|accounts|tasks|meetings|calls|deals}/{id}/	Record timeline
GET	/api/dashboard/stats/	Aggregated lead stats (range, tz)
POST	/api/dashboard/briefing/	AI "Plan my day"
GET	/api/picklists/{module}/ · {module}/{field}/	Read options
POST / PUT	/api/picklists/{module}/{field}/create/ · reorder/	SUPERADMIN: add / reorder
PATCH / DELETE	/api/picklists/options/{id}/update/ · delete/	SUPERADMIN: edit / delete
GET	/api/exports/{entity}/?format=csv|xlsx	Export leads, accounts, contacts, tasks, calls, meetings
POST	/api/mail/recipients/resolve/	Bcc batches
POST	/api/email-activity/compose/	Log "opened in Gmail"
POST	/api/validate/field/	Live phone / email duplicate check
GET / PATCH	/api/lead-capture/form/	SUPERADMIN: read / update form
POST	/api/lead-capture/form/block/ · unblock/ · regenerate-link/	SUPERADMIN: form controls
GET, POST	/api/public/lead-forms/{token}/	Public form view / submit
GET	/api/integrations/google/status/	Connection status
POST	/api/integrations/google/connect/	Start OAuth
GET	/api/integrations/google/callback/	OAuth return
DELETE	/api/integrations/google/disconnect/	Disconnect
POST	/api/internal/notifications/process/	Scheduler only (X-Cron-Secret)
</details>

A Postman collection and environment live in postman/ (Accounts, Authentication, Leads, Meetings, Users, Calls, Contacts, Email activity, Mail, Tasks, Timeline).

Quick start
Prerequisites
Python 3.12+
PostgreSQL (with permission to run CREATE EXTENSION pg_trgm; the search-index migrations do this)
(optional) Redis, a Gemini API key, a Google OAuth client

No local Postgres? One line:

bash
docker run -d --name leadpulse-db -p 5432:5432 \
  -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=postgres postgres:16
Install and run
bash
# 1. Clone and enter
git clone <your-repo-url> LMS_BACK && cd LMS_BACK

# 2. Virtual environment
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate

# 3. Dependencies
pip install -r requirements.txt

# 4. Environment (see the Configuration section for everything)
cat > .env <<'EOF'
DJANGO_SECRET_KEY=change-me-to-a-long-random-string
DJANGO_DEBUG=True

DB_NAME=leadpulse
DB_USER=postgres
DB_PASSWORD=postgres
DB_HOST=localhost
DB_PORT=5432

FRONTEND_URL=http://localhost:3000
EOF

# 5. Create the database (idempotent) and apply migrations
python scripts/create_database.py
python manage.py migrate

# 6. Create the first platform operator
python manage.py create_platform_admin --email ops@example.com --name "Platform Ops"

# 7. Run
python manage.py runserver

The API is now live at http://127.0.0.1:8000/api/. Point the frontend's NEXT_PUBLIC_API_URL at it.

Tip: generate a secret key with python -c "from django.core.management.utils import get_random_secret_key as g; print(g())"

With DJANGO_DEBUG=False (the default) the dev server does not serve admin static files; set it to True locally.

First-run walkthrough

A five-minute tour with curl (requires jq). The refresh token is stored in an HttpOnly cookie, hence -c/-b.

bash
API=http://127.0.0.1:8000/api

# 1. Log in as the platform operator
TOKEN=$(curl -s -c cookies.txt -X POST $API/auth/login/ \
  -H 'Content-Type: application/json' \
  -d '{"email":"ops@example.com","password":"<the password you set>"}' | jq -r .access_token)

# 2. Create a company together with its first SUPERADMIN
curl -s -X POST $API/platform/companies/ \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{
        "company_name": "Acme Corp",
        "website": "https://acme.example.com",
        "admin_name": "Alice Admin",
        "admin_email": "alice@acme.example.com",
        "admin_password": "at-least-8-chars"
      }' | jq

# 3. Log in as that company's SUPERADMIN
TOKEN=$(curl -s -c cookies.txt -X POST $API/auth/login/ \
  -H 'Content-Type: application/json' \
  -d '{"email":"alice@acme.example.com","password":"at-least-8-chars"}' | jq -r .access_token)

curl -s $API/users/me/ -H "Authorization: Bearer $TOKEN" | jq

# 4. Create a lead (name and phone are required)
curl -s -X POST $API/leads/create/ \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"name":"Asha Nair","company_name":"Acme","email":"asha@acme.example","phone":"9876543210","lead_source":"Web Research"}' | jq

# 5. Search and filter leads
curl -s -G $API/leads/ -H "Authorization: Bearer $TOKEN" \
  --data-urlencode 'search=asha' \
  --data-urlencode 'filters=[{"field":"lead_source","operator":"equals","value":"Web Research"}]' \
  --data-urlencode 'page_size=10' | jq

# 6. Silently refresh the access token using the cookie
curl -s -b cookies.txt -c cookies.txt -X POST $API/auth/refresh/ | jq
Configuration

All configuration is through environment variables (loaded from .env by python-dotenv). Never commit real values.

<details open> <summary><b>Core, database and cache</b></summary>
Variable	Default	Purpose
DJANGO_SECRET_KEY	required	Django signing key
DJANGO_DEBUG	False	Debug mode
DJANGO_EXTRA_ALLOWED_HOSTS	empty	Extra hosts, comma-separated (e.g. .ngrok-free.dev). localhost, 127.0.0.1 and .onrender.com are built in
APP_TIME_ZONE	Asia/Kolkata	Interprets naive datetimes, defines "today", renders API datetimes
FRONTEND_URL	none	Used in reset emails, lead-form public URLs and the Google return redirect
DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT	required	PostgreSQL connection
REDIS_URL	empty	redis://:pw@host:6379/0 or rediss://...; empty = in-process cache
CACHE_KEY_PREFIX	lms	Lets environments share one Redis
REDIS_CONNECT_TIMEOUT, REDIS_SOCKET_TIMEOUT	0.5	Fail fast so a slow Redis never stalls requests
AUTH_CACHE_TTL_SECONDS	60	User-row and suspension cache (0 = off)
COUNT_CACHE_TTL_SECONDS	600	List COUNT(*) cache (0 = off)
</details> <details> <summary><b>CORS, cookies and proxies</b></summary>
Variable	Default	Purpose
CORS_EXTRA_ALLOWED_ORIGINS	empty	Extra frontend origins, comma-separated (also added to CSRF trusted origins)
REFRESH_COOKIE_NAME	refresh_token	Refresh cookie name
REFRESH_COOKIE_PATH	/	Cookie path
REFRESH_COOKIE_DOMAIN	unset	Cookie domain
NUM_PROXIES	unset	Exact number of reverse proxies in front of the app. Needed for correct client-IP throttling; see Troubleshooting
</details> <details> <summary><b>Email (password reset)</b></summary>
Variable	Default	Purpose
EMAIL_PROVIDER	http if EMAIL_HTTP_ENDPOINT is set, else smtp	smtp or http
EMAIL_HTTP_ENDPOINT	none	HTTPS relay URL (for hosts that block SMTP ports, e.g. Render free tier)
EMAIL_HTTP_TOKEN	none	Optional bearer token for the relay
EMAIL_HOST, EMAIL_PORT, EMAIL_USE_TLS, EMAIL_HOST_USER, EMAIL_HOST_PASSWORD	587 / True for port / TLS	SMTP settings (local development)
DEFAULT_FROM_EMAIL	EMAIL_HOST_USER	Sender
EMAIL_TIMEOUT	20	Seconds; keep below gunicorn's worker timeout
</details> <details> <summary><b>Google integration and Gemini</b></summary>
Variable	Default	Purpose
GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET	empty	OAuth client (type Web application)
GOOGLE_REDIRECT_URI	empty	Must exactly match https://<backend>/api/integrations/google/callback/
GOOGLE_TOKEN_ENCRYPTION_KEY	empty	Fernet key; losing it forces users to reconnect
GOOGLE_OAUTH_STATE_MAX_AGE	600	Signed OAuth state validity (s)
GOOGLE_API_TIMEOUT	15	Google API timeout (s)
GOOGLE_FRONTEND_RETURN_PATH	/integrations/google/callback	Where the browser lands after consent
GEMINI_API_KEY	empty	Empty switches AI features off
GEMINI_MODEL	gemini-2.5-flash	Any Gemini model that accepts audio
GEMINI_TIMEOUT_SECONDS	300	Per-request timeout
GEMINI_MAX_RETRIES	2	Extra attempts after 429 / 5xx / network errors
GEMINI_MAX_OUTPUT_TOKENS	32768	Answer cap

Generate the Fernet key once:

bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
</details> <details> <summary><b>Call recordings and transcription</b></summary>
Variable	Default	Purpose
SUPABASE_STORAGE_BUCKET	empty	Set to store audio in a private Supabase bucket; empty = local MEDIA_ROOT
SUPABASE_S3_ENDPOINT, SUPABASE_S3_ACCESS_KEY_ID, SUPABASE_S3_SECRET_ACCESS_KEY	required with a bucket	S3-compatible credentials
SUPABASE_S3_REGION	us-east-1	Region
MEDIA_ROOT	./media	Local recording folder
CALL_RECORDING_MAX_MB	25	Largest upload (keep ≤ 50 on Supabase free)
CALL_RECORDING_MAX_PER_CALL	10	Recordings per call
CALL_RECORDING_STORAGE_LIMIT_MB	900 with a bucket, else 0	Total audio across all companies (0 = unlimited)
CALL_TRANSCRIPTION_AUTO	True	Transcribe each upload automatically
CALL_TRANSCRIPTION_SUMMARY_LANGUAGE	English	Summary language (the transcript keeps the spoken language)
CALL_TRANSCRIPTION_WORKERS	2	Concurrent transcriptions per process
CALL_TRANSCRIPTION_STALE_MINUTES	15	After this, an unfinished run is considered abandoned
CALL_TRANSCRIPTION_RUN_INLINE	False	Run inside the request (debugging only)
</details> <details> <summary><b>Schedulers, throttling and imports</b></summary>
Variable	Default	Purpose
NOTIFICATION_CRON_SECRET	none	Required header value (X-Cron-Secret); endpoint fails closed without it
LEAD_IMPORT_CRON_SECRET	empty	Header X-Import-Secret; empty disables the endpoint (answers 404)
LEAD_IMPORT_RETENTION_DAYS	30	Days before a finished import's stored rows are purged
LEAD_IMPORT_STALL_MINUTES	2	Inactivity before a running import is considered stalled
LEAD_CAPTURE_SUBMIT_RATE	10/hour	Public form submissions per client
LEAD_CAPTURE_VIEW_RATE	120/hour	Public form views per client
LEAD_CAPTURE_DAILY_CAP	500	Submissions per form per local day, then 410

Tunable limits read from Django settings with sensible in-code defaults: LEAD_IMPORT_MAX_BYTES (10 MB), LEAD_IMPORT_MAX_ROWS (10,000), LEAD_IMPORT_BATCH_SIZE (~500), plus the *_TIMEOUT_SECONDS values for summaries and the daily briefing. Override them in config/settings.py if needed.

</details> <details> <summary><b>Test database</b></summary>
Variable	Default	Purpose
TEST_DB_NAME, TEST_DB_USER, TEST_DB_PASSWORD	none	Used instead of DB_* whenever manage.py test runs
TEST_DB_HOST, TEST_DB_PORT	localhost, 5432	
</details>
Performance and caching

LeadPulse is built so a list screen costs one COUNT and one page query, regardless of page size.

Technique	Detail
Tenant-first composite indexes	Every list index starts (company, is_deleted, ...) then the filtered / sorted column, across leads, contacts, accounts, deals, tasks, calls, meetings and users.
Trigram search	GIN indexes on UPPER(column) (pg_trgm) for lead name / email / company, contact name / emails, account name / website / phone, and deal name, so contains searches use an index. Searches shorter than 3 characters cannot.
No N+1	Owners, accounts, contacts and hosts come from select_related; shared/tests/test_list_query_counts.py fails the build if a list starts querying per row.
Narrow reads	List endpoints use .only(...) projections and read just display names from joined tables.
Auth cache	The JWT user row and the company-suspension answer are cached (60 s default), cleared on every save / delete and again after commit. A suspension applies on the next request. Fails open when Redis is down.
Versioned count cache	The list total is cached under a per-company, per-resource version key. Any write bumps the version, instantly orphaning old totals. Only the integer is cached, never rows.
Dashboard in 4 queries	One aggregated call replaced ~15 list requests.

Redis is optional. Without it everything works with a per-process cache; the lead-capture throttles then limit per worker instead of globally. Note that DRF throttling does not fail open: a Redis outage can make the public lead-form endpoints error until it returns.

Background work and schedulers

The backend has no Celery and needs no extra worker process: Render-style hosting stays simple. Two things run outside the request cycle:

1. External cron (HTTP)

Job	Request	Header	Frequency
Notification processing	POST /api/internal/notifications/process/	X-Cron-Secret	every minute
Lead-import maintenance	POST /api/leads/import/maintenance/	X-Import-Secret	every 5 minutes
Use cron-job.org (a ready-to-adapt job definition is in docs/cron-job.org.config.json) or any scheduler that can send a POST with a custom header.
Notification responses carry counters (reminders_processed, task_notifications_created, calls_marked_missed, failures, ...). 401 = wrong secret, 405 = not POST, 500 = at least one company failed (the others are still processed, so the scheduler can alert).
The import maintenance call resumes stalled imports, deletes drafts older than 24 h, purges expired stored rows, and marks long-stuck imports failed, all in about 20 seconds, and is safe to run concurrently.

2. In-process thread pool

Call transcription runs in a small thread pool inside the web process. Queued work is in memory, so a deploy can drop it; the transcript then stays PENDING / PROCESSING until CALL_TRANSCRIPTION_STALE_MINUTES passes, after which it is requeued on the next POST. The TranscriptionDispatcher interface lets you swap in a real task queue without touching a single use case. The lead-import docs include a ready Celery sketch too.

Management commands
Command	Purpose
python manage.py create_platform_admin --email E --name N [--password P]	Create the first PLATFORM_SUPERADMIN (idempotent; omit --password to be prompted)
python manage.py process_notifications	Run the notification engine once (same use case as the cron endpoint)
python manage.py audit_tenant_data	Report rows with missing / inconsistent companies; exits 1 if any
python manage.py check_duplicate_emails	List user emails that collide when compared case-insensitively, with their user ids; exits 1 if any
python scripts/create_database.py	Create the PostgreSQL database named in DB_NAME if it does not exist
Testing
bash
# all tests (needs the TEST_DB_* variables, see below)
python manage.py test

# a single module
python manage.py test src.modules.deals

# a single file or case
python manage.py test src.modules.deals.test_deals_stage_rules
Tests run on PostgreSQL (trigram indexes, row locks and FOR UPDATE behaviour must match production). Provide TEST_DB_NAME, TEST_DB_USER, TEST_DB_PASSWORD (and optionally TEST_DB_HOST / TEST_DB_PORT). Django creates a throw-away test_<name> database, so the user needs CREATEDB.
When test is in sys.argv the settings automatically switch to the test database, use the in-memory cache, and set AUTH_CACHE_TTL_SECONDS and COUNT_CACHE_TTL_SECONDS to 0 so tests see database changes immediately. A test that needs a cache uses override_settings(COUNT_CACHE_TTL_SECONDS=600).
What is covered: domain rules (deal stages, call states), use cases with fakes, repository filters, permission matrices, tenant isolation per module, platform hardening, lead import (validation, duplicates, owners, files, conversion), Gemini adapters, Google OAuth / Fernet, Redis cache behaviour, and query-count regression guards.
Tests live next to the code (test_*.py) or in a module's tests/ package.
Deployment

The repo is tuned for Render (web service) with the frontend on Vercel, but nothing is Render-specific.

1. Build and start

bash
# Build command (build.sh)
./build.sh            # collectstatic --no-input && migrate --no-input

# Start command
gunicorn config.wsgi:application

2. Required environment (see Configuration): DJANGO_SECRET_KEY, DJANGO_DEBUG=False, DB_*, FRONTEND_URL, NOTIFICATION_CRON_SECRET, and an email route that works on your host (EMAIL_HTTP_ENDPOINT on hosts that block SMTP).

3. Production checklist

[ ] DJANGO_DEBUG=False and a long random DJANGO_SECRET_KEY
[ ] PostgreSQL reachable; the DB user may CREATE EXTENSION pg_trgm (migrations run it)
[ ] FRONTEND_URL set to your real frontend origin
[ ] Frontend origins added through CORS_EXTRA_ALLOWED_ORIGINS, and the preview-deployment regex in config/settings.py adjusted to your Vercel team slug (or removed)
[ ] NUM_PROXIES set to the exact number of proxies in front of Django (so the public-form throttle sees real client IPs and cannot be dodged with a forged X-Forwarded-For)
[ ] REDIS_URL set (shared throttles, auth cache and count cache across workers)
[ ] SUPABASE_STORAGE_BUCKET (+ S3 credentials) set so recordings survive deploys, because platform disks are ephemeral; the bucket must be private
[ ] GEMINI_API_KEY set, ideally a billed key, since call audio contains customer data (see the privacy note in docs/call-transcription-api.md)
[ ] Google OAuth redirect URI registered exactly as GOOGLE_REDIRECT_URI; GOOGLE_TOKEN_ENCRYPTION_KEY backed up
[ ] cron-job.org jobs created for notifications (1 min) and import maintenance (5 min)
[ ] First operator created with python manage.py create_platform_admin ...
[ ] python manage.py audit_tenant_data returns clean after any data migration

Free-tier instances sleep; the first request after a quiet period can take ~30 s. A one-minute notification cron keeps the service warm as a side effect.

Project structure
LMS_BACK/
├── config/
│   ├── settings.py            # all configuration, env-driven
│   ├── urls.py                # mounts every module under /api/
│   ├── wsgi.py / asgi.py
├── src/modules/
│   ├── accounts/  authentication/  calendar/  calls/  companies/
│   ├── contacts/  dashboard/  deals/  email_activity/  exports/
│   ├── google_integration/  lead_capture/  leads/  mailing/  meetings/
│   ├── notifications/  picklists/  reminders/  shared/  tasks/
│   └── timeline/  users/       # each: domain / application / infrastructure / presentation
├── docs/                      # API contracts and operations guides (see index below)
├── postman/                   # Postman collections and environment
├── scripts/create_database.py
├── staticfiles/               # collectstatic output
├── build.sh                   # collectstatic + migrate
├── manage.py
└── requirements.txt
Documentation index

Detailed, example-driven contracts live in docs/:

Area	File
User management (login, me, list, edit, block, retire, audit)	user-management-api.md
Platform: companies	platform-companies-api.md
Platform: users, audit log, overview	platform-admin-api.md
Deals (stages, board, forecast, convert-with-deal)	deals-api.md
Calls	calls-api.md
Call recordings	call-recordings-api.md
Call transcription (Gemini)	call-transcription-api.md
Google Meet and Calendar	google-meet-api.md
Lead import	lead_import.md
Lead capture form	lead-capture-api.md
AI summaries	lead-summary-api.md, contact-summary-api.md, account-summary-api.md
Daily briefing	daily-briefing-api.md
Dashboard	dashboard-api.md
Export	export-api.md
Mail recipients and email activity	mail-recipients-api.md, email-activity-api.md
Password-reset email delivery	password_reset_email.md
Notification cron	notification-cron.md, render-notification-cron.md, cron-job-org.md
Redis cache	redis-cache.md
Query performance and indexes	query-performance.md
Behaviour-change log	CHANGES-backend-fixes.md
Extending the codebase

Adding a new feature module? Follow the same shape so everything stays consistent:

Domain: add entities / enums under domain/ (plain Python, no framework imports).
Ports: declare repository and service interfaces in application/interfaces/.
Use cases: one class per action in application/use_cases/, taking interfaces in __init__ and raising ValueError for business-rule violations.
Persistence: add the Django model and a repository in infrastructure/persistence/. The repository must take company_id and filter every query by it. Add composite indexes starting with (company, is_deleted, ...).
Presentation: serializers, thin APIViews with permission_classes = [IsAuthenticated, IsCompanyUser, ...], a dependencies/*_dependencies.py factory that receives a TenantContext, and urls.py.
Wire up: register the app in INSTALLED_APPS and include its URLs in config/urls.py.
Record activity: call the timeline recorder from create / update / delete use cases.
Invalidate caches: if the module has a paginated list, add a count_cache_invalidation signal module like the others.
Test: at minimum a happy path, a permission matrix, and a tenant-isolation test proving another company gets 404; add a query-count assertion if you add a list.
Document: add an API contract to docs/.
Troubleshooting
Symptom	Likely cause and fix
ImproperlyConfigured: The SECRET_KEY setting must not be empty.	DJANGO_SECRET_KEY is not set in .env / the environment.
Browser says "Method PATCH is not allowed by Access-Control-Allow-Methods"	Preflight cached from an old build; methods are explicit in settings and the preflight cache is 10 minutes, so hard-refresh or wait.
403 "A company account is required."	You are calling company endpoints with a PLATFORM_SUPERADMIN token. Log in as a company user.
403 mentioning suspension	The company is SUSPENDED; reactivate it from the platform console.
Refresh works locally but not cross-site in production	HTTPS is required for SameSite=None; Secure. Make sure the proxy sends X-Forwarded-Proto: https and your frontend origin is in the CORS list.
Password-reset email never arrives on Render	Render's free tier blocks SMTP. Use EMAIL_PROVIDER=http with EMAIL_HTTP_ENDPOINT; see docs/password_reset_email.md.
Reset log says "returned a web page instead of a result" or HTTP 401 ... HTML	The relay web app is not public ("Anyone"); redeploy it as a new version.
Transcript endpoints answer 503	GEMINI_API_KEY is not set.
Transcript stuck on PENDING / PROCESSING after a deploy	The in-memory queue was lost; after CALL_TRANSCRIPTION_STALE_MINUTES, POST .../transcript/ requeues it.
Recording upload fails on Supabase	Check bucket name, endpoint, keys, and that CALL_RECORDING_MAX_MB ≤ the plan's per-file limit.
/api/leads/import/maintenance/ returns an empty 404	LEAD_IMPORT_CRON_SECRET is unset (endpoint disabled) or the X-Import-Secret header is wrong.
Notification cron returns 401	X-Cron-Secret does not match NOTIFICATION_CRON_SECRET.
Public lead form throttling hits everyone at once	NUM_PROXIES is unset behind a proxy, so all visitors share the proxy's IP. Set it to the exact proxy count.
Public lead-form endpoints error while Redis is down	DRF throttling does not fail open (the auth and count caches do). Restore Redis.
Migration fails with a permissions error on pg_trgm	The DB role cannot create extensions. Create it once as a superuser: CREATE EXTENSION IF NOT EXISTS pg_trgm;
manage.py test cannot connect	TEST_DB_* variables are missing, or the role lacks CREATEDB.
Admin pages have no CSS in production	Static files are collected into staticfiles/ but this project does not configure a static-file server in MIDDLEWARE; serve staticfiles/ from your platform or add WhiteNoise middleware.
Another user's record returns 404	Working as designed: records from other companies behave as if they do not exist.
License

No license has been declared for this repository yet. Add a LICENSE file before distributing it.
