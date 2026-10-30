"""Excel and CSV files of the lead import: the template, the downloads, and
the round trip back through the upload parser."""

import csv
import io
from unittest import TestCase

import openpyxl

from src.modules.leads.application.services.lead_import_files import (
    build_stream,
    clean_cell,
    rejected_columns,
    safe_cell,
)
from src.modules.leads.application.services.lead_import_parser import parse_upload
from src.modules.leads.application.use_cases.import_template import (
    BuildImportTemplateUseCase,
)

HEADERS = ["Name", "Mobile Number", "Notes", "Amount"]
RAW_ROWS = [
    ["Jane Doe", "+91 98765 43210", '=HYPERLINK("http://evil","x")', "-500"],
    ["Zoë Ünïcode", "0098765", "line1\nline2", "@SUM(A1)"],
    ["Ctl\x07Char", "9876543210", "#N/A", "1,234.50"],
]
EXPECTED = [
    {"Name": "Jane Doe", "Mobile Number": "+91 98765 43210", "Notes": '=HYPERLINK("http://evil","x")', "Amount": "-500"},
    {"Name": "Zoë Ünïcode", "Mobile Number": "0098765", "Notes": "line1\nline2", "Amount": "@SUM(A1)"},
    {"Name": "CtlChar", "Mobile Number": "9876543210", "Notes": "#N/A", "Amount": "1,234.50"},
]


def _download(file_format):
    columns = rejected_columns(HEADERS)
    rows = [clean_row + ["Problem text", "How to fix text"] for clean_row in
            ([clean_cell(v) for v in row] for row in RAW_ROWS)]
    stream = build_stream(file_format, columns, iter(rows), "Rejected rows", wide_columns=("Problem", "How to fix"))
    return b"".join(stream), stream


class XlsxDownloadTests(TestCase):
    def test_is_a_real_workbook_with_header_and_frozen_row(self):
        data, stream = _download("xlsx")
        self.assertEqual(data[:2], b"PK")
        self.assertIn("spreadsheetml.sheet", stream.content_type)
        sheet = openpyxl.load_workbook(io.BytesIO(data)).active
        self.assertEqual(sheet.title, "Rejected rows")
        self.assertEqual(sheet.freeze_panes, "A2")
        self.assertEqual([c.value for c in sheet[1]], HEADERS + ["Problem", "How to fix"])
        self.assertTrue(sheet["A1"].font.bold)

    def test_nothing_is_a_formula_and_nothing_gets_a_visible_quote(self):
        data, _ = _download("xlsx")
        sheet = openpyxl.load_workbook(io.BytesIO(data)).active
        for row in sheet.iter_rows(min_row=2):
            for cell in row:
                self.assertEqual(cell.data_type, "s", cell.coordinate)
        self.assertEqual(sheet["B2"].value, "+91 98765 43210")
        self.assertEqual(sheet["C2"].value, '=HYPERLINK("http://evil","x")')
        self.assertEqual(sheet["D2"].value, "-500")
        self.assertEqual(sheet["C4"].value, "#N/A")  # not turned into an error cell

    def test_control_characters_are_dropped(self):
        data, _ = _download("xlsx")
        sheet = openpyxl.load_workbook(io.BytesIO(data)).active
        self.assertEqual(sheet["A4"].value, "CtlChar")

    def test_downloaded_file_uploads_back_unchanged(self):
        data, _ = _download("xlsx")
        parsed = parse_upload(io.BytesIO(data), "clients-rejected.xlsx")
        self.assertEqual([r["values"] for r in parsed.rows],
                         [dict(e, **{"Problem": "Problem text", "How to fix": "How to fix text"}) for e in EXPECTED])

    def test_a_long_cell_is_cut_to_the_excel_limit(self):
        self.assertEqual(len(clean_cell("a" * 40_000)), 32_000)


class CsvDownloadTests(TestCase):
    def test_has_bom_and_guards_formula_starts(self):
        data, stream = _download("csv")
        self.assertTrue(data.startswith(b"\xef\xbb\xbf"))
        self.assertIn("text/csv", stream.content_type)
        records = list(csv.reader(io.StringIO(data.decode("utf-8-sig"), newline="")))
        self.assertEqual(records[1][1], "'+91 98765 43210")
        self.assertEqual(records[1][3], "'-500")
        self.assertEqual(safe_cell("=1+1"), "'=1+1")
        self.assertEqual(safe_cell("plain"), "plain")

    def test_downloaded_file_uploads_back_unchanged(self):
        data, _ = _download("csv")
        parsed = parse_upload(io.BytesIO(data), "clients-rejected.csv")
        self.assertEqual([{k: r["values"][k] for k in HEADERS} for r in parsed.rows], EXPECTED)


class TemplateTests(TestCase):
    def setUp(self):
        self.use_case = BuildImportTemplateUseCase()

    def test_xlsx_template_opens_and_uploads_back(self):
        file = self.use_case.execute("xlsx")
        self.assertEqual(file.file_name, "lead_import_template.xlsx")
        self.assertIn("spreadsheetml.sheet", file.content_type)
        sheet = openpyxl.load_workbook(io.BytesIO(file.content)).active
        headers = [c.value for c in sheet[1]]
        self.assertEqual(sheet.max_row, 2)
        parsed = parse_upload(io.BytesIO(file.content), file.file_name)
        self.assertEqual(parsed.headers, headers)
        self.assertEqual(parsed.total_rows, 1)

    def test_csv_template_is_the_default(self):
        self.assertEqual(self.use_case.execute(None).file_name, "lead_import_template.csv")

    def test_unknown_format_is_refused(self):
        from src.modules.leads.application.use_cases.lead_import_common import ImportRequestError

        with self.assertRaises(ImportRequestError):
            self.use_case.execute("pdf")


class ParserExcelTests(TestCase):
    def _book(self, fill):
        workbook = openpyxl.Workbook()
        fill(workbook)
        buffer = io.BytesIO()
        workbook.save(buffer)
        return io.BytesIO(buffer.getvalue())

    def test_numeric_cells_keep_their_digits(self):
        def fill(wb):
            ws = wb.active
            ws.append(["Name", "Mobile Number", "Postal Code"])
            ws.append(["A", 9876543210, 682016])
            ws.append(["B", 9.87654321e9, "012345"])

        parsed = parse_upload(self._book(fill), "a.xlsx")
        self.assertEqual(parsed.rows[0]["values"]["Mobile Number"], "9876543210")
        self.assertEqual(parsed.rows[1]["values"]["Mobile Number"], "9876543210")
        self.assertEqual(parsed.rows[1]["values"]["Postal Code"], "012345")

    def test_header_row_and_sheet_choice(self):
        def fill(wb):
            wb.active.title = "Cover"
            wb.active.append(["nothing here"])
            ws = wb.create_sheet("Leads")
            ws.append(["Report"])
            ws.append(["Name", "Email"])
            ws.append(["A", "a@x.com"])

        parsed = parse_upload(self._book(fill), "a.xlsx", header_row=2, sheet_name="Leads")
        self.assertEqual(parsed.headers, ["Name", "Email"])
        self.assertEqual(parsed.rows[0]["row_number"], 3)
        self.assertEqual(parsed.sheet_names, ["Cover", "Leads"])
