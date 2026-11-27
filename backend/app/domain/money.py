"""Exact money handling (decision D-07). No binary floating point anywhere."""
import re
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

RULE_VERSION = "R1-2026-11-27"
ROUNDING = ROUND_HALF_UP

# ISO 4217 minor units for currencies supported at organisation creation.
CURRENCY_MINOR_UNITS: dict[str, int] = {
    "AUD": 2,
    "NPR": 2,
    "NZD": 2,
    "USD": 2,
    "GBP": 2,
    "EUR": 2,
    "INR": 2,
    "SGD": 2,
}

ZERO = Decimal("0")

_THOUSANDS = re.compile(r"\d{1,3}(,\d{3})+(\.\d+)?")


class MoneyError(ValueError):
    pass


def quantum(currency: str) -> Decimal:
    return Decimal(1).scaleb(-CURRENCY_MINOR_UNITS[currency])


def parse_amount(value: object, currency: str, *, allow_negative: bool = False) -> Decimal:
    """Parse a user/imported amount without ever rounding it.

    Accepts strings such as "1,100.00", "$1100", "(50.00)" (negative), and Decimal/int.
    Floats are rejected outright to avoid binary representation errors.
    """
    if isinstance(value, float):
        raise MoneyError("Amount must not be a binary floating-point number")
    if isinstance(value, Decimal):
        d = value
    elif isinstance(value, int):
        d = Decimal(value)
    elif isinstance(value, str):
        s = value.strip()
        if not s:
            raise MoneyError("Amount is empty")
        negative = False
        if s.startswith("(") and s.endswith(")"):
            negative, s = True, s[1:-1].strip()
        for symbol in ("AU$", "A$", "$", "Rs.", "Rs", "रू", "₹", "£", "€", "AUD", "NPR"):
            s = s.replace(symbol, "")
        s = s.replace(" ", "")
        if s.startswith("-"):
            negative, s = (not negative), s[1:]
        if "," in s:
            # Only thousands separators are accepted (e.g. 1,100.00). Ambiguous formats such as
            # "1.100,00" or "1,10" are rejected rather than guessed.
            if not _THOUSANDS.fullmatch(s):
                raise MoneyError(f"'{value}' uses an unsupported number format; use 1,100.00 or 1100.00")
            s = s.replace(",", "")
        try:
            d = Decimal(s)
        except InvalidOperation as exc:
            raise MoneyError(f"'{value}' is not a valid amount") from exc
        if negative:
            d = -d
    else:
        raise MoneyError(f"Unsupported amount type {type(value).__name__}")
    if not d.is_finite():
        raise MoneyError("Amount must be a finite number")
    places = CURRENCY_MINOR_UNITS[currency]
    exponent = d.as_tuple().exponent
    if isinstance(exponent, int) and -exponent > places and d != d.quantize(quantum(currency)):
        raise MoneyError(f"Amount has more than {places} decimal places; values are never rounded on import")
    if d < 0 and not allow_negative:
        raise MoneyError("Amount must not be negative")
    if abs(d) >= Decimal("1e15"):
        raise MoneyError("Amount is too large")
    return d.quantize(quantum(currency))


def round_money(d: Decimal, currency: str) -> Decimal:
    """Explicit rounding boundary (derived values only)."""
    return d.quantize(quantum(currency), rounding=ROUNDING)


def fmt(d: Decimal | None, currency: str) -> str | None:
    """Serialise money for APIs and exports as an exact string at currency precision."""
    if d is None:
        return None
    return str(d.quantize(quantum(currency)))


def round_metric(d: Decimal, places: int = 1) -> Decimal:
    return d.quantize(Decimal(1).scaleb(-places), rounding=ROUNDING)
