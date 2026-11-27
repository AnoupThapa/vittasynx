"""Untrusted file parsing (security.md §File handling).

- Only .csv and .xlsx are accepted; macro-enabled (.xlsm) and legacy (.xls) files are rejected.
- XLSX is opened read-only with cached values only (formulas and macros are never executed).
- Size, decompressed size and row-count limits guard against resource exhaustion.
- Every cell becomes a string so the raw source value is preserved exactly. Numeric XLSX cells use
  the shortest round-trip representation (repr) so no float arithmetic ever touches amounts.
"""
from __future__ import annotations

import csv
import io
import zipfile
from dataclasses import dataclass
from datetime import date, datetime, time

from app.config import get_settings
from app.core.errors import ValidationFailed


@dataclass
class ParsedFile:
    headers: list[str]
    rows: list[tuple[int, dict[str, str]]]  # (spreadsheet line number, {header: raw string})
    content_type: str


def _cell_to_str(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, datetime):
        if value.time() == time(0, 0):
            return value.date().isoformat()
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, float):
        text = repr(value)
        return text[:-2] if text.endswith(".0") else text
    return str(value).strip()


def _unique_headers(raw: list[str]) -> list[str]:
    seen: dict[str, int] = {}
    out = []
    for i, h in enumerate(raw, start=1):
        name = (h or "").strip() or f"Column {i}"
        if name in seen:
            seen[name] += 1
            name = f"{name} ({seen[name]})"
        else:
            seen[name] = 1
        out.append(name)
    return out


def _finish(header_row: list[str], data_rows, content_type: str) -> ParsedFile:
    limit = get_settings().max_import_rows
    headers = _unique_headers(header_row)
    rows: list[tuple[int, dict[str, str]]] = []
    for line_no, values in data_rows:
        if all(not v for v in values):
            continue  # blank line
        if len(rows) >= limit:
            raise ValidationFailed(f"The file has more than {limit} rows; split it into smaller files",
                                   code="too_many_rows")
        padded = list(values) + [""] * (len(headers) - len(values))
        extra = [v for v in padded[len(headers):] if v]
        if extra:
            raise ValidationFailed(f"Line {line_no} has more values than there are column headers",
                                   code="malformed_file")
        rows.append((line_no, dict(zip(headers, padded[: len(headers)]))))
    if not headers:
        raise ValidationFailed("The file has no header row", code="empty_file")
    return ParsedFile(headers, rows, content_type)


def parse(filename: str, data: bytes) -> ParsedFile:
    s = get_settings()
    if len(data) == 0:
        raise ValidationFailed("The file is empty", code="empty_file")
    if len(data) > s.max_upload_bytes:
        raise ValidationFailed(f"The file is larger than {s.max_upload_bytes // (1024 * 1024)} MB", code="file_too_large")
    name = filename.lower()
    if name.endswith(".csv"):
        return _parse_csv(data)
    if name.endswith(".xlsx"):
        return _parse_xlsx(data)
    raise ValidationFailed("Only .csv and .xlsx files are supported (macro-enabled and .xls files are not)",
                           code="unsupported_file_type")


def _parse_csv(data: bytes) -> ParsedFile:
    if data.startswith(b"PK\x03\x04"):
        raise ValidationFailed("This looks like a spreadsheet, not a CSV; save it as .xlsx", code="file_type_mismatch")
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValidationFailed("The CSV is not UTF-8 encoded; export it as 'CSV UTF-8'", code="invalid_encoding") from exc
    if "\x00" in text:
        raise ValidationFailed("The file contains binary data", code="file_type_mismatch")
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    reader = csv.reader(io.StringIO(text), dialect)
    try:
        all_rows = [[c.strip() for c in row] for row in reader]
    except csv.Error as exc:
        raise ValidationFailed(f"The CSV could not be read: {exc}", code="malformed_file") from exc
    if not all_rows:
        raise ValidationFailed("The file is empty", code="empty_file")
    return _finish(all_rows[0], [(i + 2, r) for i, r in enumerate(all_rows[1:])], "text/csv")


def _parse_xlsx(data: bytes) -> ParsedFile:
    s = get_settings()
    if not data.startswith(b"PK\x03\x04"):
        raise ValidationFailed("The file is not a valid .xlsx workbook", code="file_type_mismatch")
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            names = zf.namelist()
            if sum(i.file_size for i in zf.infolist()) > s.max_xlsx_uncompressed_bytes:
                raise ValidationFailed("The workbook expands to an unsafe size", code="file_too_large")
            if any(n.lower().endswith("vbaproject.bin") for n in names):
                raise ValidationFailed("Macro-enabled workbooks are not accepted", code="macros_not_allowed")
            if "xl/workbook.xml" not in names:
                raise ValidationFailed("The file is not a valid .xlsx workbook", code="file_type_mismatch")
    except zipfile.BadZipFile as exc:
        raise ValidationFailed("The file is not a valid .xlsx workbook", code="file_type_mismatch") from exc

    from openpyxl import load_workbook  # imported lazily; parsing only

    try:
        wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    except Exception as exc:  # noqa: BLE001 - openpyxl raises many types for malformed input
        raise ValidationFailed("The workbook could not be read", code="malformed_file") from exc
    try:
        ws = wb.worksheets[0]
        rows_iter = ws.iter_rows(values_only=True)
        header = next(rows_iter, None)
        if header is None:
            raise ValidationFailed("The workbook's first sheet is empty", code="empty_file")
        header_strs = [_cell_to_str(h) for h in header]
        while header_strs and not header_strs[-1]:
            header_strs.pop()
        data_rows = []
        for i, row in enumerate(rows_iter, start=2):
            values = [_cell_to_str(v) for v in row]
            data_rows.append((i, values))
            if len(data_rows) > s.max_import_rows + 1000:  # stop early on huge sheets
                break
        return _finish(header_strs, data_rows, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    finally:
        wb.close()
