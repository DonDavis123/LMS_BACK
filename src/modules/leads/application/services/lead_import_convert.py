"""Rows of a lead import that are marked "converted" (Account + Contact).

PART 10 REPLACES THIS FILE. Until then every converted row is skipped with a
clear note, so nothing is half done and the counts stay honest.

The processor calls ``convert_outcomes`` once per batch, INSIDE the batch
transaction, with the batch's CONVERT outcomes. Part 10 may write to the
database here; if it raises, the whole batch (leads included) is rolled back
and retried, so converted rows are never half imported.
"""

from __future__ import annotations

from dataclasses import dataclass

RESULT_CONVERTED = "converted"
RESULT_SKIPPED = "skipped"
RESULT_FAILED = "failed"

NOT_ENABLED_NOTE = (
    "Importing converted leads as an Account and a Contact is not available yet, "
    "so this row was skipped."
)


@dataclass(frozen=True)
class ConvertRowResult:
    result: str  # converted | skipped | failed
    note: str | None = None


def convert_outcomes(job, outcomes, *, tenant_context=None, runtime=None) -> dict[int, ConvertRowResult]:
    """``{row_number: ConvertRowResult}`` for every outcome handed in.

    ``job`` is the locked job, ``outcomes`` the batch's CONVERT ``RowOutcome``
    objects (payload, owner and original values are on them), ``runtime`` the
    repositories the processor itself uses.
    """
    return {
        outcome.row_number: ConvertRowResult(RESULT_SKIPPED, NOT_ENABLED_NOTE)
        for outcome in outcomes
    }
