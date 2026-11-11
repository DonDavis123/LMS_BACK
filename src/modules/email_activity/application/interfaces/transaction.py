from __future__ import annotations

from typing import Callable, Protocol, TypeVar

T = TypeVar("T")


class TransactionPort(Protocol):
    """All-or-nothing execution; the project's transaction manager fits."""

    def execute(self, operation: Callable[[], T]) -> T: ...
