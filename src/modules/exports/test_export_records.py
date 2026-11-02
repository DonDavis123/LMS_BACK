import io
from datetime import datetime, timezone as dt_timezone
from types import SimpleNamespace

from django.test import SimpleTestCase
from openpyxl import load_workbook

from src.modules.exports.application.services.export_definitions import (
    DEFINITIONS,
    ExportColumn,
    ExportDefinition,
)
from src.modules.exports.application.services.export_file_writer import (
    parse_format,
)
from src.modules.exports.application.use_cases.export_records import (
    ExportRecordsUseCase,
    ExportTooLargeError,
)
from src.modules.shared.application.dto.list_query import (
    FilterCondition,
    ListQuery,
    PaginatedResult,
)


class FakeListUseCase:
    """Serves ``rows`` page by page, like a list use case."""

    def __init__(self, rows):
        self.rows = rows
        self.queries = []

    def execute(self, query):
        self.queries.append(query)
        start = (query.page - 1) * query.page_size
        return PaginatedResult(
            results=self.rows[start:start + query.page_size],
            page=query.page,
            page_size=query.page_size,
            total=len(self.rows),
        )


DEFINITION = ExportDefinition(
    key="things",
    file_prefix="things",
    sheet_title="Things",
    columns=(
        ExportColumn("Name", lambda r: r["name"]),
        ExportColumn("Count", lambda r: r["count"]),
    ),
)
NOW = datetime(2026, 11, 2, 14, 30)


def body(download) -> bytes:
    return b"".join(download.stream)


class ExportRecordsUseCaseTests(SimpleTestCase):
    def rows(self, n):
        return [{"name": f"Row {i}", "count": i} for i in range(n)]

    def test_csv_has_header_and_every_row_across_pages(self):
        fake = FakeListUseCase(self.rows(120))  # 3 pages of 50
        download = ExportRecordsUseCase(fake, DEFINITION).execute(
            ListQuery(page=7, page_size=5), "csv", NOW
        )
        text = body(download).decode("utf-8-sig")
        lines = text.strip().split("\r\n")

        self.assertEqual(lines[0], "Name,Count")
        self.assertEqual(len(lines), 121)
        self.assertEqual(lines[-1], "Row 119,119")
        self.assertEqual(download.total, 120)
        self.assertEqual([q.page for q in fake.queries], [1, 2, 3])
        self.assertTrue(all(q.page_size == 50 for q in fake.queries))

    def test_file_name_and_default_format(self):
        download = ExportRecordsUseCase(FakeListUseCase([]), DEFINITION).execute(
            ListQuery(), None, NOW
        )
        self.assertEqual(download.file_name, "things-20261102-1430.csv")
        self.assertEqual(body(download).decode("utf-8-sig").strip(), "Name,Count")

    def test_search_filters_and_sort_are_passed_to_the_list(self):
        fake = FakeListUseCase(self.rows(3))
        query = ListQuery(
            search="abc",
            filters=(FilterCondition("name", "contains", "x"),),
            sort_by="name",
            sort_direction="asc",
        )
        body(ExportRecordsUseCase(fake, DEFINITION).execute(query, "csv", NOW))

        sent = fake.queries[0]
        self.assertEqual(sent.search, "abc")
        self.assertEqual(sent.filters, query.filters)
        self.assertEqual((sent.sort_by, sent.sort_direction), ("name", "asc"))

    def test_xlsx_is_a_real_workbook(self):
        download = ExportRecordsUseCase(FakeListUseCase(self.rows(3)), DEFINITION).execute(
            ListQuery(), "xlsx", NOW
        )
        self.assertTrue(download.file_name.endswith(".xlsx"))
        sheet = load_workbook(io.BytesIO(body(download))).active

        self.assertEqual(sheet.title, "Things")
        self.assertEqual(
            [[c.value for c in row] for row in sheet.iter_rows()],
            [["Name", "Count"], ["Row 0", 0], ["Row 1", 1], ["Row 2", 2]],
        )

    def test_formula_text_is_never_a_formula(self):
        rows = [{"name": "=SUM(1,1)", "count": 1}, {"name": "+91 98765 43210", "count": 2}]

        csv_text = body(
            ExportRecordsUseCase(FakeListUseCase(rows), DEFINITION).execute(ListQuery(), "csv", NOW)
        ).decode("utf-8-sig")
        self.assertIn('"\'=SUM(1,1)",1', csv_text)
        self.assertIn("'+91 98765 43210,2", csv_text)

        sheet = load_workbook(
            io.BytesIO(
                body(ExportRecordsUseCase(FakeListUseCase(rows), DEFINITION).execute(ListQuery(), "xlsx", NOW))
            )
        ).active
        self.assertEqual(sheet["A2"].value, "=SUM(1,1)")
        self.assertEqual(sheet["A2"].data_type, "s")
        self.assertEqual(sheet["A3"].value, "+91 98765 43210")

    def test_too_many_rows_is_refused_before_a_file_starts(self):
        use_case = ExportRecordsUseCase(FakeListUseCase(self.rows(5)), DEFINITION, max_rows=4)
        with self.assertRaises(ExportTooLargeError):
            use_case.execute(ListQuery(), "csv", NOW)

    def test_unknown_format_is_a_value_error(self):
        with self.assertRaises(ValueError):
            ExportRecordsUseCase(FakeListUseCase([]), DEFINITION).execute(ListQuery(), "pdf", NOW)
        self.assertEqual(parse_format(" XLSX "), "xlsx")

    def test_filters_are_refused_when_the_list_has_none(self):
        no_filters = ExportDefinition(
            key="m", file_prefix="m", sheet_title="M",
            columns=DEFINITION.columns, supports_filters=False,
        )
        query = ListQuery(filters=(FilterCondition("a", "eq", 1),))
        with self.assertRaises(ValueError):
            ExportRecordsUseCase(FakeListUseCase([]), no_filters).execute(query, "csv", NOW)


class ExportDefinitionTests(SimpleTestCase):
    def test_every_entity_is_defined(self):
        self.assertEqual(
            set(DEFINITIONS),
            {"leads", "accounts", "contacts", "tasks", "calls", "meetings"},
        )

    def test_lead_columns_read_a_lead_row(self):
        row = SimpleNamespace(
            name="Asha", company_name="Acme", email="a@x.com", phone=None,
            mobile_number="9999999999", lead_source="Web", lead_status="New",
            owner=SimpleNamespace(name="Owner One"),
            created_at=datetime(2026, 11, 2, 4, 0, tzinfo=dt_timezone.utc),
            updated_at=datetime(2026, 11, 2, 4, 0, tzinfo=dt_timezone.utc),
        )
        values = [c.getter(row) for c in DEFINITIONS["leads"].columns]

        self.assertEqual(values[0], "Asha")
        self.assertEqual(values[7], "Owner One")
        self.assertEqual(values[8], "2026-11-02 09:30")  # Asia/Kolkata
