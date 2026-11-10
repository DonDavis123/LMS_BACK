from dataclasses import dataclass


@dataclass(frozen=True)
class MarkMissedCallsResult:
    marked: int = 0
    failures: int = 0
