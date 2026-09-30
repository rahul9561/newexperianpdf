import pytest

from experian_pdf import formatters as fmt


@pytest.mark.parametrize("raw,expected", [
    ("20260531", "2026-05-31"),
    ("2026-05-31", "2026-05-31"),
    (20260531, "2026-05-31"),
    (None, "-"),
    ("", "-"),
    ("   ", "-"),
    ("00000000", "00000000"),  # unparseable -> raw
    ("31/05/26", "31/05/26"),
])
def test_date_ymd(raw, expected):
    assert fmt.date_ymd(raw) == expected


def test_date_display_and_time():
    assert fmt.date_display("20260612") == "12-06-2026"
    assert fmt.time_hms("172052") == "17:20:52"
    assert fmt.time_hms(None) == "-"


@pytest.mark.parametrize("raw,expected", [
    ("123456", "1,23,456"),
    ("3252600", "32,52,600"),
    ("100000000", "10,00,00,000"),
    ("999", "999"),
    ("1000", "1,000"),
    ("0", "0"),
    ("-150000", "-1,50,000"),
    ("1234.5", "1,234.50"),
    (1234567, "12,34,567"),
])
def test_indian_number(raw, expected):
    assert fmt.indian_number(raw) == expected


@pytest.mark.parametrize("raw,expected", [
    ("123456", "₹1,23,456"),
    ("3252600", "₹32,52,600"),
    (None, "-"),
    ("", "-"),
    ("n/a", "n/a"),
])
def test_currency_inr(raw, expected):
    assert fmt.currency_inr(raw) == expected


@pytest.mark.parametrize("raw,expected", [
    ("0001319695", "1319695"), (1319695, "1319695"), ("12.50", "12.5"), (None, "-"), ("", "-"),
])
def test_amount_plain(raw, expected):
    assert fmt.amount(raw) == expected


@pytest.mark.parametrize("empty", [None, "", "  ", [], {}])
def test_dash_for_empty(empty):
    assert fmt.text(empty) == "-"
    assert fmt.upper(empty) == "-"
    assert fmt.amount(empty) == "-"
    assert fmt.date_ymd(empty) == "-"
    assert fmt.strip_zeros(empty) == "-"
    assert fmt.mask(empty) == "-"
    assert fmt.code_label(empty, {"1": "x"}) == "-"
    assert fmt.join_nonempty([empty, empty]) == "-"


def test_misc():
    assert fmt.rate("10.990") == "10.99"
    assert fmt.rate("9.000") == "9"
    assert fmt.strip_zeros("01") == "1"
    assert fmt.strip_zeros("000") == "0"
    assert fmt.mask("ABCDEFGH1234") == "XXXXXXXX1234"
    assert fmt.code_label("1", {"01": "Male"}) == "Male"
    assert fmt.code_label("01", {"1": "Male"}) == "Male"
    assert fmt.code_label("zz", {"1": "Male"}) == "zz"
    assert fmt.join_nonempty(["A", None, " ", "B"]) == "A B"
