"""Writes an export as a CSV or XLSX file that is sent in small chunks.

Pure Python plus ``openpyxl``: no Django and no database access. Rows arrive
as an iterator, so a large export is never held in memory as a whole.

* CSV: UTF-8 with a byte-order mark (so Excel shows accents correctly).
* XLSX: openpyxl write-only mode into a temporary file that is read back in
  chunks.

A spreadsheet must never run a cell as a formula:

* CSV: text that starts with ``=``, ``+``, ``-`` or ``@`` gets a leading single
  quote;
* XLSX: text is always written as a plain string cell.
"""

from __future__ import annotations

import csv
import io
import os
import re
import tempfile
from dataclasses import dataclass
from typing import Callable, Iterable, Iterator

FORMAT_CSV = "csv"
FORMAT_XLSX = "xlsx"
FORMATS = (FORMAT_CSV, FORMAT_XLSX)

CONTENT_TYPES = {
    FORMAT_CSV: "text/csv; charset=utf-8",
    FORMAT_XLSX: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}

BOM = b"\xef\xbb\xbf"
CHUNK_BYTES = 64 * 1024
MAX_CELL_LENGTH = 32_000  # Excel allows 32,767 characters in a cell
_FORMULA_STARTS = ("=", "+", "-", "@")
_ILLEGAL_XML = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def parse_format(value) -> str:
    """``csv`` (default) or ``xlsx``; anything else is a ``ValueError``."""
    if value is None or not str(value).strip():
        return FORMAT_CSV
    chosen = str(value).strip().lower()
    if chosen not in FORMATS:
        raise ValueError("The format parameter must be 'csv' or 'xlsx'.")
    return chosen


def clean_cell(value):
    """One cell: ``None`` becomes empty text, numbers stay numbers, text loses
    control characters and is cut to the Excel cell limit."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, (int, float)):
        return value
    text = value if isinstance(value, str) else str(value)
    text = _ILLEGAL_XML.sub("", text)
    if len(text) > MAX_CELL_LENGTH:
        text = text[:MAX_CELL_LENGTH]
    return text


def csv_safe(value):
    """A CSV cell that Excel can't run as a formula (text only)."""
    if isinstance(value, str) and value.startswith(_FORMULA_STARTS):
        return "'" + value
    return value


@dataclass
class FileStream:
    """A file that is read out in chunks. ``close`` removes any temp file."""

    chunks: Iterator[bytes]
    content_type: str
    close: Callable[[], None] = lambda: None

    def __iter__(self):
        try:
            yield from self.chunks
        finally:
            self.close()


def csv_stream(columns: list[str], rows: Iterable[list]) -> FileStream:
    def generate():
        buffer = io.StringIO(newline="")
        writer = csv.writer(buffer, lineterminator="\r\n")
        yield BOM
        writer.writerow([csv_safe(clean_cell(column)) for column in columns])
        for row in rows:
            writer.writerow([csv_safe(clean_cell(cell)) for cell in row])
            if buffer.tell() >= CHUNK_BYTES:
                yield buffer.getvalue().encode("utf-8")
                buffer.seek(0)
                buffer.truncate(0)
        if buffer.tell():
            yield buffer.getvalue().encode("utf-8")

    return FileStream(generate(), CONTENT_TYPES[FORMAT_CSV])


def xlsx_stream(
    columns: list[str],
    rows: Iterable[list],
    sheet_title: str,
) -> FileStream:
    """Builds the workbook first (write-only, so it stays small), then reads
    it back in chunks."""
    from openpyxl import Workbook
    from openpyxl.cell import WriteOnlyCell
    from openpyxl.styles import Font
    from openpyxl.utils import get_column_letter

    handle = tempfile.NamedTemporaryFile(prefix="export-", suffix=".xlsx", delete=False)
    path = handle.name
    handle.close()

    def cleanup():
        try:
            os.remove(path)
        except OSError:
            pass

    try:
        workbook = Workbook(write_only=True)
        sheet = workbook.create_sheet(title=sheet_title[:31])
        sheet.freeze_panes = "A2"
        for index in range(1, len(columns) + 1):
            sheet.column_dimensions[get_column_letter(index)].width = 22

        def text_cell(text: str, bold: bool = False):
            """openpyxl turns text starting with ``=`` into a formula; force a
            plain string cell instead."""
            cell = WriteOnlyCell(sheet, value=text)
            cell.data_type = "s"
            if bold:
                cell.font = Font(bold=True)
            return cell

        sheet.append([text_cell(str(clean_cell(column)), bold=True) for column in columns])
        for row in rows:
            cells = []
            for value in map(clean_cell, row):
                if isinstance(value, str) and value[:1] in ("=", "#", "+", "-", "@"):
                    cells.append(text_cell(value))
                else:
                    cells.append(value)
            sheet.append(cells)
        workbook.save(path)
    except Exception:
        cleanup()
        raise

    def generate():
        with open(path, "rb") as source:
            while True:
                chunk = source.read(CHUNK_BYTES)
                if not chunk:
                    break
                yield chunk

    return FileStream(generate(), CONTENT_TYPES[FORMAT_XLSX], close=cleanup)


def build_stream(
    file_format: str,
    columns: list[str],
    rows: Iterable[list],
    sheet_title: str,
) -> FileStream:
    if file_format == FORMAT_XLSX:
        return xlsx_stream(columns, rows, sheet_title)
    return csv_stream(columns, rows)
