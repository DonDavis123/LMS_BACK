import os
from uuid import UUID

from src.modules.leads.application.services.lead_import_fields import (
    IMPORT_FIELDS,
    suggest_mapping_detailed,
)
from src.modules.leads.application.services.lead_import_mapping import IGNORE
from src.modules.leads.application.services.lead_import_options import ImportOptions
from src.modules.leads.application.services.lead_import_parser import (
    ImportFileError,
    parse_upload,
)
from src.modules.leads.application.services.lead_import_review import (
    SAMPLE_ROW_COUNT,
    STAGE_DRAFT,
    import_limits,
)

MAX_FILE_NAME_LENGTH = 255


def _clean_file_name(name: str | None) -> str:
    base = os.path.basename((name or "").replace("\\", "/")).strip() or "import"
    if len(base) <= MAX_FILE_NAME_LENGTH:
        return base
    stem, extension = os.path.splitext(base)
    return stem[: MAX_FILE_NAME_LENGTH - len(extension)] + extension


def _header_row(raw) -> int:
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return 1
    try:
        return int(str(raw).strip())
    except ValueError:
        raise ImportFileError(
            "invalid_header_row",
            "The header row must be a whole number.",
            "Enter the row number that holds your column names (usually 1).",
        )


class UploadImportFileUseCase:
    """Reads the file and keeps it as a draft import. Nothing is imported."""

    def __init__(self, job_repository, created_by_id: UUID):
        self.job_repository = job_repository
        self.created_by_id = created_by_id

    def execute(self, file_obj, file_name, header_row=None, sheet_name=None) -> dict:
        if file_obj is None:
            raise ImportFileError(
                "file_missing",
                "No file was uploaded.",
                "Choose a .csv or .xlsx file and upload it in the 'file' field.",
            )

        limits = import_limits()
        size = getattr(file_obj, "size", None)
        if size == 0:
            raise ImportFileError(
                "empty_file",
                "The file is empty.",
                "Check that you chose the right file and that it contains a header row and data.",
            )
        # The parser repeats this check and also caps what it reads.
        if isinstance(size, int) and size > limits["max_bytes"]:
            megabytes = limits["max_bytes"] // (1024 * 1024)
            raise ImportFileError(
                "file_too_large",
                f"The file is larger than {megabytes} MB.",
                "Split the file into smaller files, or remove unused columns and sheets, "
                "and upload again.",
            )

        name = _clean_file_name(file_name)
        chosen_sheet = sheet_name.strip() if isinstance(sheet_name, str) and sheet_name.strip() else None
        parsed = parse_upload(
            file_obj,
            name,
            header_row=_header_row(header_row),
            sheet_name=chosen_sheet,
        )

        suggestions = suggest_mapping_detailed(parsed.headers)
        mapping = {
            header: (item["field"] or IGNORE) for header, item in suggestions.items()
        }
        options = ImportOptions().to_dict()
        options["stage"] = STAGE_DRAFT

        job = self.job_repository.create(
            created_by_id=self.created_by_id,
            file_name=name,
            headers=parsed.headers,
            header_row=parsed.header_row,
            sheet_name=parsed.sheet_name,
            mapping=mapping,
            options=options,
            rows=parsed.rows,
            total_rows=parsed.total_rows,
        )

        return {
            "job_id": str(job.id),
            "file_name": name,
            "total_rows": parsed.total_rows,
            "headers": parsed.headers,
            "sheet_names": parsed.sheet_names,
            "header_row": parsed.header_row,
            "sheet_name": parsed.sheet_name,
            "warnings": parsed.warnings,
            "suggested_mapping": suggestions,
            "sample_rows": parsed.rows[:SAMPLE_ROW_COUNT],
            "fields": [
                {
                    "key": field.key,
                    "label": field.label,
                    "required": field.required,
                    "kind": field.kind,
                }
                for field in IMPORT_FIELDS
            ],
            "limits": limits,
        }
