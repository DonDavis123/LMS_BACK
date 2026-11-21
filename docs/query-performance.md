# List query performance

## Indexes
Every list filters on `company_id` (tenant) and `is_deleted`, so the composite
indexes start with those columns, then the filtered / sorted column.

| Table | Indexes |
|---|---|
| leads | `(company, is_deleted, is_converted, owner / lead_status / lead_source)` |
| contacts | `(company, is_deleted, created_at / contact_owner / account)` |
| accounts | `(company, is_deleted, created_at / account_owner)` |
| deals | `(company, is_deleted, created_at / owner / account / contact)` |
| tasks | `(company, is_deleted, created_at / status / due_date / owner / assigned_to)` |
| calls | `(company, is_deleted, call_start_time / status)` |
| meetings | `(company, is_deleted, start_at / created_at / end_at / host)` |
| users | `(company, deleted_at, created_at)` |

Most of these already existed as migrations but were missing from the models'
`Meta.indexes`; they are now declared so `makemigrations` does not drop them.
New migrations: `tasks/0006`, `deals/0003`, `meetings/0012`.

## Fewer queries
Every list page is one COUNT plus one page query (meetings: plus two batched
queries for related records / participants). Owner, account, contact, lead and
host names come from `select_related` joins, never one query per row.
`shared/tests/test_list_query_counts.py` fails if a list starts querying per row.

## Fewer columns
- Leads, contacts, accounts: `.only(LIST_COLUMNS)` and a `_to_list_domain`
  mapper. Columns the list does not show are `None` on the returned entity.
- Deals, tasks, calls: the whole row is returned by the API, but joined tables
  read only the display name (`list_columns()` in
  `shared/infrastructure/persistence/list_projection.py`).
- Meetings: only the columns the table shows; the host join reads the name only.
