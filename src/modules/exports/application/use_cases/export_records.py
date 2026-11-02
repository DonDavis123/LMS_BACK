from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from typing import Iterator, Protocol

from src.modules.exports.application.services.export_definitions import (
    ExportDefinition,
)
from src.modules.exports.application.services.export_file_writer import (
    FileStream,
    build_stream,
    parse_format,
)
from src.modules.shared.application.dto.list_query import ListQuery

# The list use cases refuse a page larger than ListQuery.MAX_PAGE_SIZE.
PAGE_SIZE = ListQuery.MAX_PAGE_SIZE
MAX_EXPORT_ROWS = 10_000


class ExportTooLargeError(ValueError):
    """The filtered list has more rows than one export may hold."""


class ListUseCase(Protocol):
    def execute(self, query: ListQuery): ...


@dataclass
class ExportDownload:
    file_name: str
    stream: FileStream
    total: int


class ExportRecordsUseCase:
    """Exports a list as a CSV or XLSX file.

    It reads the records through the same list use case the screen uses, so
    the search, filters, sort order, tenant scoping and permissions are exactly
    those of the list. Pages are read one after the other while the file is
    written, so a large export is never held in memory as a whole.
    """

    def __init__(
        self,
        list_use_case: ListUseCase,
        definition: ExportDefinition,
        max_rows: int = MAX_EXPORT_ROWS,
    ):
        self.list_use_case = list_use_case
        self.definition = definition
        self.max_rows = max_rows

    def execute(self, query: ListQuery, file_format: str | None, now: datetime) -> ExportDownload:
        chosen_format = parse_format(file_format)

        if query.filters and not self.definition.supports_filters:
            raise ValueError(f"{self.definition.key.title()} filtering is not supported.")

        # Page and page size of the screen do not matter: everything that
        # matches is exported. The first page is read now so a bad filter or
        # sort field fails before any file is started.
        first_query = replace(query, page=1, page_size=PAGE_SIZE)
        first_page = self.list_use_case.execute(first_query)

        if first_page.total > self.max_rows:
            raise ExportTooLargeError(
                f"This export has {first_page.total} rows, more than the limit of "
                f"{self.max_rows}. Narrow the search or filters and try again."
            )

        columns = [column.header for column in self.definition.columns]
        stream = build_stream(
            chosen_format,
            columns,
            self._rows(first_query, first_page),
            self.definition.sheet_title,
        )
        file_name = f"{self.definition.file_prefix}-{now.strftime('%Y%m%d-%H%M')}.{chosen_format}"
        return ExportDownload(file_name=file_name, stream=stream, total=first_page.total)

    def _rows(self, first_query: ListQuery, first_page) -> Iterator[list]:
        getters = [column.getter for column in self.definition.columns]

        def to_row(record) -> list:
            return [getter(record) for getter in getters]

        for record in first_page.results:
            yield to_row(record)

        for page_number in range(2, first_page.total_pages + 1):
            page = self.list_use_case.execute(replace(first_query, page=page_number))
            if not page.results:
                break
            for record in page.results:
                yield to_row(record)
