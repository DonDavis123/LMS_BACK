"""What happens once, when an import reaches its end.

PART 11 FILLS THIS IN (one summary timeline entry and one notification).

``finalize_job`` is called exactly once per job, right after the transaction
that finished it has been committed, whichever way it ended: completed,
cancelled (``job.options["stage"] == "cancelled"``, status still completed) or
failed. Errors raised here are logged and swallowed by the caller; they never
change the import's result. Part 11 should therefore be safe to run twice
(for example by recording ``finalized_at`` on the job) in case a retry is ever
added.
"""

from __future__ import annotations


def finalize_job(job, runtime=None) -> None:
    """Stub: does nothing yet."""
    return None
