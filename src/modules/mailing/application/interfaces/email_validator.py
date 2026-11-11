from typing import Protocol


class EmailValidator(Protocol):
    """Tells whether an address is well formed (the address is already trimmed)."""

    def __call__(self, address: str) -> bool: ...
