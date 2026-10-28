from uuid import UUID

from src.modules.leads.application.services.lead_import_options import (
    MAX_ROW_NUMBERS,
    ImportOptions,
    validate_options,
)
from src.modules.leads.application.services.lead_import_pipeline import is_excluded
from src.modules.leads.application.services.lead_import_review import with_server_keys
from src.modules.leads.application.use_cases.lead_import_common import (
    ImportRequestError,
    load_draft,
    require_rows,
)
from src.modules.shared.application.tenant_context import TenantContext


def _invalid(message: str, how_to_fix: str) -> ImportRequestError:
    return ImportRequestError("invalid_exclusions", message, how_to_fix)


def _row_numbers(raw, name: str) -> list[int]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise _invalid(
            f"{name} must be a list of row numbers.",
            f"Send {name} as a list like [12, 15].",
        )
    if len(raw) > MAX_ROW_NUMBERS:
        raise _invalid(
            f"{name} has more than {MAX_ROW_NUMBERS:,} row numbers.",
            "Use an exclusion rule instead of listing so many rows.",
        )
    numbers = []
    for item in raw:
        if isinstance(item, bool) or not isinstance(item, int) or item < 1:
            raise _invalid(
                f"'{item}' in {name} is not a valid row number.",
                "Use the row numbers shown in your file (whole numbers of 1 or more).",
            )
        numbers.append(item)
    return numbers


class UpdateImportExclusionsUseCase:
    """Saves which rows to leave out of the import.

    The check is NOT updated here. Leaving a row out can change other rows
    (a later row stops being an in-file duplicate, and the owner rotation
    shifts), so the only correct way to get new counts is the full check,
    which is quick. The saved check becomes outdated and the client must call
    validate again. The number of rows the exclusions match is returned
    straight away because it is exact and needs no database.
    """

    def __init__(self, job_repository, tenant_context: TenantContext):
        self.job_repository = job_repository
        self.tenant_context = tenant_context

    def execute(self, job_id: UUID, body: dict) -> dict:
        job = load_draft(self.job_repository, self.tenant_context, job_id)
        rows = require_rows(job)

        known = {"row_numbers_add", "row_numbers_remove", "rules", "skip_rows_with_errors"}
        if not isinstance(body, dict) or not (known & set(body)):
            raise _invalid(
                "Nothing to change.",
                "Send row_numbers_add, row_numbers_remove, rules or skip_rows_with_errors.",
            )

        to_add = _row_numbers(body.get("row_numbers_add"), "row_numbers_add")
        to_remove = _row_numbers(body.get("row_numbers_remove"), "row_numbers_remove")
        file_rows = {row["row_number"] for row in rows}
        unknown = sorted(set(to_add) - file_rows)
        if unknown:
            shown = ", ".join(str(n) for n in unknown[:10])
            raise _invalid(
                f"These rows are not in your file: {shown}.",
                "Use the row numbers shown in the rows list.",
            )

        current = ImportOptions.from_dict(job.options).exclusions
        numbers = [n for n in current["row_numbers"] if n not in set(to_remove)]
        for number in to_add:
            if number not in numbers:
                numbers.append(number)

        rules = current["rules"]
        if "rules" in body:
            if not isinstance(body["rules"], list) or any(
                not isinstance(rule, dict) for rule in body["rules"]
            ):
                raise _invalid(
                    "rules must be a list of rules.",
                    "Send each rule as {column, operator, value}.",
                )
            rules = body["rules"]

        skip_errors = current["skip_rows_with_errors"]
        if "skip_rows_with_errors" in body:
            if not isinstance(body["skip_rows_with_errors"], bool):
                raise _invalid(
                    "skip_rows_with_errors must be true or false.",
                    "Send true to leave out rows with errors, or false to keep them.",
                )
            skip_errors = body["skip_rows_with_errors"]

        exclusions = ImportOptions.from_dict(
            {
                "exclusions": {
                    "row_numbers": numbers,
                    "rules": rules,
                    "skip_rows_with_errors": skip_errors,
                }
            }
        ).exclusions
        problems = validate_options(
            ImportOptions(exclusions=exclusions), list(job.headers or [])
        )
        if problems:
            raise _invalid(problems[0], "Fix the exclusion and try again.")

        options = with_server_keys(
            {**ImportOptions.from_dict(job.options).to_dict(), "exclusions": exclusions},
            job.options,
        )
        self.job_repository.save_progress(job, {"options": options})

        by_number = 0
        by_rule = 0
        manual = set(exclusions["row_numbers"])
        rule_only = {"row_numbers": [], "rules": exclusions["rules"]}
        for row in rows:
            number = row["row_number"]
            if number in manual:
                by_number += 1
            elif is_excluded(row.get("values") or {}, number, rule_only)[0]:
                by_rule += 1

        return {
            "exclusions": exclusions,
            "excluded_by_number": by_number,
            "excluded_by_rules": by_rule,
            "needs_validate": True,
            "message": (
                "Saved. Run the check again to see the new counts: leaving rows out "
                "can change duplicates and owner assignment for other rows."
            ),
        }
