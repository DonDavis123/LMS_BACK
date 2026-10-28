import csv
import io
from dataclasses import dataclass

from src.modules.leads.application.services.lead_import_fields import IMPORT_FIELDS
from src.modules.leads.application.use_cases.lead_import_common import ImportRequestError

FORMAT_CSV = "csv"
FORMAT_XLSX = "xlsx"

CSV_CONTENT_TYPE = "text/csv; charset=utf-8"
XLSX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

# One example row. Dropdown values are only examples: use the options your
# company has set up.
EXAMPLE_VALUES = {
    "name": "Jane Doe",
    "title": "Sales Manager",
    "company_name": "Acme Traders Pvt Ltd",
    "email": "jane.doe@example.com",
    "mobile_number": "9876543210",
    "phone": "04842345678",
    "lead_source": "Website",
    "lead_status": "New",
    "industry": "Technology",
    "rating": "Warm",
    "website": "https://www.example.com",
    "number_of_employees": "50",
    "annual_revenue": "5000000",
    "address": "12 MG Road",
    "city": "Kochi",
    "state": "Kerala",
    "country": "India",
    "postal_code": "682016",
    "description": "Asked for a product demo",
    "owner": "owner@yourcompany.com",
    "converted": "No",
}


@dataclass(frozen=True)
class ImportTemplateFile:
    content: bytes
    content_type: str
    file_name: str


class BuildImportTemplateUseCase:
    """A blank import file: one header per importable field and one example row."""

    def execute(self, file_format: str | None) -> ImportTemplateFile:
        chosen = (file_format or FORMAT_CSV).strip().lower()
        headers = [field.label for field in IMPORT_FIELDS]
        example = [EXAMPLE_VALUES.get(field.key, "") for field in IMPORT_FIELDS]

        if chosen == FORMAT_CSV:
            return ImportTemplateFile(
                self._csv(headers, example), CSV_CONTENT_TYPE, "lead_import_template.csv"
            )
        if chosen == FORMAT_XLSX:
            return ImportTemplateFile(
                self._xlsx(headers, example), XLSX_CONTENT_TYPE, "lead_import_template.xlsx"
            )
        raise ImportRequestError(
            "invalid_template_format",
            f"The template format '{chosen}' is not available.",
            "Use format=csv or format=xlsx.",
        )

    @staticmethod
    def _csv(headers: list[str], example: list[str]) -> bytes:
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(headers)
        writer.writerow(example)
        # UTF-8 with a BOM so Excel opens non-English text correctly.
        return ("\ufeff" + buffer.getvalue()).encode("utf-8")

    @staticmethod
    def _xlsx(headers: list[str], example: list[str]) -> bytes:
        try:
            from openpyxl import Workbook
            from openpyxl.styles import Font
        except ImportError as exc:
            raise ImportRequestError(
                "xlsx_unavailable",
                "Excel templates are not available on this server.",
                "Download the CSV template instead.",
            ) from exc

        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Leads"
        sheet.append(headers)
        sheet.append(example)
        for cell in sheet[1]:
            cell.font = Font(bold=True)
        for index, header in enumerate(headers, start=1):
            letter = sheet.cell(row=1, column=index).column_letter
            sheet.column_dimensions[letter].width = max(16, len(header) + 4)

        buffer = io.BytesIO()
        workbook.save(buffer)
        return buffer.getvalue()
