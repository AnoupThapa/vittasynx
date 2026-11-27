"""Identity normalisation rules (D-09, D-15) and date parsing."""
import re
from datetime import date, datetime

_WS = re.compile(r"\s+")


def normalise_name(name: str) -> str:
    """Trim, case-fold and collapse internal whitespace. No fuzzy matching."""
    return _WS.sub(" ", name.strip()).casefold()


def normalise_number(number: str) -> str:
    """Invoice/credit note numbers: trim, upper-case, remove internal whitespace."""
    return _WS.sub("", number.strip()).upper()


DATE_FORMATS = {
    "YYYY-MM-DD": "%Y-%m-%d",
    "DD/MM/YYYY": "%d/%m/%Y",
    "MM/DD/YYYY": "%m/%d/%Y",
    "DD-MM-YYYY": "%d-%m-%Y",
    "DD.MM.YYYY": "%d.%m.%Y",
}


class DateParseError(ValueError):
    pass


def parse_date(value: object, fmt: str) -> date:
    """Parse a business date in the explicitly chosen format. Ambiguous input is never guessed."""
    if isinstance(value, datetime):
        if value.time() != datetime.min.time():
            raise DateParseError("Date contains a time component")
        return value.date()
    if isinstance(value, date):
        return value
    if value is None or (isinstance(value, str) and not value.strip()):
        raise DateParseError("Date is empty")
    if not isinstance(value, str):
        raise DateParseError(f"'{value}' is not a date")
    s = value.strip()
    # XLSX cells converted to text sometimes carry a midnight time.
    for suffix in (" 00:00:00", "T00:00:00"):
        if s.endswith(suffix):
            s = s[: -len(suffix)]
    try:
        pattern = DATE_FORMATS[fmt]
    except KeyError as exc:
        raise DateParseError(f"Unsupported date format setting {fmt}") from exc
    try:
        return datetime.strptime(s, pattern).date()
    except ValueError:
        # ISO dates are accepted regardless of the chosen format because they are unambiguous.
        try:
            return datetime.strptime(s, "%Y-%m-%d").date()
        except ValueError as exc:
            raise DateParseError(f"'{value}' is not a valid date in format {fmt}") from exc
