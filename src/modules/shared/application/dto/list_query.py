from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class FilterCondition:
    field: str
    operator: str
    value: Any


@dataclass(frozen=True)
class ListQuery:
    filters: tuple[FilterCondition, ...] = ()
    page: int = 1
    page_size: int = 20
    sort_by: str | None = None
    sort_direction: str = "desc"
    search: str | None = None

    MAX_PAGE_SIZE = 50
    MAX_SEARCH_LENGTH = 100

    def __post_init__(self) -> None:
        if self.page < 1:
            raise ValueError("Page must be greater than or equal to 1.")
        if self.page_size < 1:
            raise ValueError("Page size must be greater than or equal to 1.")
        if self.page_size > self.MAX_PAGE_SIZE:
            raise ValueError(
                f"Page size must be less than or equal to {self.MAX_PAGE_SIZE}."
            )
        if self.sort_direction not in {"asc", "desc"}:
            raise ValueError("Sort direction must be 'asc' or 'desc'.")
        if self.search is not None and len(self.search) > self.MAX_SEARCH_LENGTH:
            raise ValueError(
                f"Search must be at most {self.MAX_SEARCH_LENGTH} characters."
            )


from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")






@dataclass(frozen=True)
class PaginatedResult(Generic[T]):
    results: list[T]
    page: int
    page_size: int
    total: int

    @property
    def total_pages(self) -> int:
        if self.total == 0:
            return 0

        return (self.total + self.page_size - 1) // self.page_size