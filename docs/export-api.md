# Export API

Download a list as a CSV or Excel (XLSX) file. The export reads the records
through the same list use case the screen uses, so it applies the same
company scoping, search, filters and sort order, and it returns **every** row
that matches (not just one page).

```
GET /api/exports/<entity>/
```

| `<entity>` | Same data as            | Who can export                      |
|------------|-------------------------|-------------------------------------|
| `leads`    | `GET /api/leads/`       | SUPERADMIN, ADMIN (as the lead list) |
| `accounts` | `GET /api/accounts/`    | any company user                    |
| `contacts` | `GET /api/contacts/`    | any company user                    |
| `tasks`    | `GET /api/tasks/`       | any company user                    |
| `calls`    | `GET /api/calls/`       | any company user                    |
| `meetings` | `GET /api/meetings/`    | any company user (no filters, like the list) |

## Query parameters

| Parameter                     | Meaning                                              |
|-------------------------------|------------------------------------------------------|
| `format`                      | `csv` (default) or `xlsx`                            |
| `search`                      | same as the list                                     |
| `filters`                     | same JSON array as the list                          |
| `sort_by`, `sort_direction`   | same as the list                                     |
| `page`, `page_size`           | ignored; the whole result is exported                |

Example: `GET /api/exports/leads/?format=xlsx&search=acme&filters=[{"field":"lead_status","operator":"equals","value":"New"}]`

## Response

* `200` with the file. `Content-Disposition: attachment; filename="leads-20261102-1430.csv"`
  (already exposed to the browser by `CORS_EXPOSE_HEADERS`).
* `400 {"detail": "..."}` for a bad `format`, bad filters or sort field, or when
  the result has more than **10,000** rows
  (`MAX_EXPORT_ROWS` in `application/use_cases/export_records.py`) — narrow the
  search or filters and try again.
* `401` not signed in, `403` no permission (or platform superadmin / suspended
  company), `404` unknown entity.

## Notes

* CSV is UTF-8 with a byte-order mark so Excel shows accents correctly.
* Text beginning with `=`, `+`, `-` or `@` is neutralised so a spreadsheet never
  runs it as a formula.
* Date-times are written in the project time zone (`APP_TIME_ZONE`).
* Columns are defined in `application/services/export_definitions.py`.
