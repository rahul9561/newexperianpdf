"""Pure value formatters. Every function accepts anything and never raises."""

from __future__ import annotations

import logging
from decimal import Decimal, InvalidOperation

logger = logging.getLogger(__name__)

DASH = "-"


def is_empty(value) -> bool:
    return value is None or (isinstance(value, str) and not value.strip()) or value == [] or value == {}


def text(value, default: str = DASH) -> str:
    """Stringify and strip; empty -> ``default``."""
    if is_empty(value):
        return default
    if isinstance(value, (dict, list)):
        return default
    return str(value).strip()


def upper(value) -> str:
    return text(value).upper()


def date_ymd(value) -> str:
    """``20260531`` -> ``2026-05-31`` (sample format). Unparseable -> raw text."""
    s = text(value, "")
    if not s:
        return DASH
    digits = s.replace("-", "").replace("/", "")
    if len(digits) == 8 and digits.isdigit() and digits != "00000000":
        return f"{digits[0:4]}-{digits[4:6]}-{digits[6:8]}"
    logger.warning("Unrecognised date value %r", value)
    return s


def date_display(value) -> str:
    """``20260612`` -> ``12-06-2026`` (alternative format, not used by the sample layout)."""
    ymd = date_ymd(value)
    if len(ymd) == 10 and ymd[4] == "-":
        return f"{ymd[8:10]}-{ymd[5:7]}-{ymd[0:4]}"
    return ymd


def time_hms(value) -> str:
    """``172052`` -> ``17:20:52``."""
    s = text(value, "")
    if not s:
        return DASH
    if len(s) == 6 and s.isdigit():
        return f"{s[0:2]}:{s[2:4]}:{s[4:6]}"
    return s


def to_decimal(value) -> Decimal | None:
    s = text(value, "").replace(",", "")
    if not s:
        return None
    try:
        return Decimal(s)
    except InvalidOperation:
        return None


def to_int(value) -> int | None:
    d = to_decimal(value)
    if d is None:
        return None
    try:
        return int(d)
    except (ValueError, OverflowError):
        return None


def amount(value) -> str:
    """Plain amount exactly like the sample: ``0001319695`` -> ``1319695``."""
    d = to_decimal(value)
    if d is None:
        return text(value)
    if d == d.to_integral_value():
        return str(int(d))
    return format(d.normalize(), "f")


def indian_number(value) -> str:
    """``3252600`` -> ``32,52,600`` (Indian digit grouping)."""
    d = to_decimal(value)
    if d is None:
        return text(value)
    negative = d < 0
    d = abs(d)
    whole = int(d)
    frac = d - whole
    s = str(whole)
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        s = ",".join(groups) + "," + tail
    if frac:
        s += "." + f"{frac:.2f}"[2:]
    return ("-" if negative else "") + s


def currency_inr(value) -> str:
    """``3252600`` -> ``₹32,52,600``."""
    s = indian_number(value)
    return s if s == DASH or not s[-1].isdigit() else f"₹{s}"


def rate(value) -> str:
    """``10.990`` -> ``10.99``; ``9.000`` -> ``9``."""
    d = to_decimal(value)
    if d is None:
        return text(value)
    return format(d.normalize(), "f") if d != d.to_integral_value() else str(int(d))


def strip_zeros(value) -> str:
    """Numeric code without leading zeros: ``01`` -> ``1``, ``000`` -> ``0``."""
    s = text(value, "")
    if not s:
        return DASH
    if s.isdigit():
        return str(int(s))
    return s


def mask(value, visible: int = 4, char: str = "X") -> str:
    """Mask all but the last ``visible`` characters. Already-masked values pass through."""
    s = text(value, "")
    if not s:
        return DASH
    if len(s) <= visible:
        return s
    return char * (len(s) - visible) + s[-visible:]


def code_label(value, table: dict, field: str = "code", fallback_raw: bool = True) -> str:
    """Look up a bureau code; tries the raw code and its zero-padded / stripped forms."""
    s = text(value, "")
    if not s:
        return DASH
    candidates = [s]
    if s.isdigit():
        candidates += [s.zfill(2), str(int(s))]
    for c in candidates:
        if c in table:
            return table[c]
    logger.warning("Unknown %s code %r", field, value)
    return s if fallback_raw else DASH


def join_nonempty(parts, sep: str = " ") -> str:
    out = [str(p).strip() for p in parts if not is_empty(p) and not isinstance(p, (dict, list))]
    return sep.join(out) if out else DASH
