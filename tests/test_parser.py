import copy
import json

import pytest
from conftest import load_fixture, load_sample, profile

from experian_pdf import InvalidReportError, parse_report
from experian_pdf.parser import as_list, find_profile

DUMMY = load_fixture("dummy_report")


@pytest.fixture
def report():
    return copy.deepcopy(DUMMY)


# ------------------------------------------------------------------ values (dummy fixture)

def test_header_and_applicant(report):
    ctx = parse_report(report)
    assert ctx["header"] == {"report_date": "20260101", "report_time": "101500",
                             "report_number": "1000000000001"}
    assert ctx["applicant"]["name"] == "TESTFIRST TESTLAST"
    assert ctx["applicant"]["pan"] == "ABCDE1234F"
    assert ctx["applicant"]["mobile"] == "9000000001"
    assert ctx["applicant"]["dob"] == "1990-01-15"
    assert ctx["applicant"]["aadhaar"] == "-"


def test_score_and_summary(report):
    ctx = parse_report(report)
    assert ctx["score"] == {"value": 742, "display": "742"}
    s = ctx["summary"]
    assert (s["total"], s["active"], s["closed"], s["default"]) == ("3", "2", "1", "0")
    assert s["balance_all"] == "900000"
    assert s["caps"] == ["0", "2", "2", "2"]
    assert s["non_caps"] == ["0", "1", "1", "1"]


def test_accounts(report):
    ctx = parse_report(report)
    assert len(ctx["accounts"]) == 3
    a = ctx["accounts"][0]
    assert (a["sr"], a["account_type"], a["status"]) == ("Acc1", "HOUSING LOAN", "ACTIVE")
    assert a["date_reported"] == "2025-12-31"
    assert a["holder_name"] == "TESTFIRST TESTLAST"
    assert a["address"] == "FLAT 101 TEST RESIDENCY SAMPLE ROAD TESTCITY MAHARASHTRA 400001"
    assert a["personal"] == {"dob": "1990-01-15", "gender": "Female", "occupation": "Salaried",
                             "email": "TEST.USER@EXAMPLE.COM"}
    assert a["phone_rows"] == [[{"type": "1", "number": "9000000001", "ext": "-"},
                                {"type": "3", "number": "02200000000", "ext": "12"}]]
    assert a["ids"][0] == {"type": "PAN", "number": "ABCDE1234F", "issue": "-", "expiry": "-"}
    assert dict(a["terms"])["Rate of Interest:"] == "11.5"
    assert dict(a["description"])["Loan Type:"] == "HOUSING LOAN"
    assert dict(a["description"])["SuitFiled Willful Default:"] == "No Suit Filed"
    assert dict(a["terms"])["Ownership:"] == "Individual"

    card = ctx["accounts"][1]
    assert card["account_type"] == "CREDIT CARD" and card["overdue"] == "4500"
    assert card["history"][0]["year"] == "2025"
    assert card["history"][0]["cells"][10] == {"value": "30", "cls": "late"}  # Nov 2025
    assert card["history"][0]["cells"][11] == {"value": "0", "cls": "ok"}     # Dec 2025

    closed = ctx["accounts"][2]
    assert closed["status"] == "CLOSED"
    assert dict(closed["terms"])["Date Closed:"] == "2023-06-30"


def test_enquiries(report):
    ctx = parse_report(report)
    assert len(ctx["enquiries"]) == 2
    e = ctx["enquiries"][0]
    assert e["name"] == "TESTFIRST TESTLAST"
    assert e["address"] == "FLAT 101 TEST RESIDENCY SAMPLE ROAD TESTCITY MAHARASHTRA 400001"
    col3 = dict(e["col3"])
    assert col3["Credit Institution Name"] == "Test Finance 1 Private Limited"
    assert col3["Application Date"] == "2025-12-01"
    assert col3["Amount Applied For"] == "100000"
    assert dict(e["col1"])["Gender"] == "Female"


def test_payment_history_colours():
    ctx = parse_report(load_fixture("many_accounts"))
    cells = [c for c in ctx["accounts"][3]["history"][0]["cells"] if c]
    classes = {c["value"]: c["cls"] for c in cells}
    assert classes["0"] == "ok" and classes["30"] == "late" and classes["60"] == "late"
    assert classes["95"] == "bad" and classes["120"] == "bad"
    assert classes["L"] == "bad"  # DPD missing -> asset classification letter shown


def test_sample_json_structure():
    """The real sample parses; expected values are read from the JSON, not hard-coded."""
    data = load_sample()
    r = profile(data)
    ctx = parse_report(data)
    assert len(ctx["accounts"]) == len(r["CAIS_Account"]["CAIS_Account_DETAILS"])
    assert ctx["score"]["display"] == r["SCORE"]["BureauScore"]
    assert ctx["header"]["report_number"] == r["CreditProfileHeader"]["ReportNumber"]
    assert ctx["summary"]["total"] == r["CAIS_Account"]["CAIS_Summary"]["Credit_Account"]["CreditAccountTotal"]
    assert ctx["enquiries"] == []


# ------------------------------------------------------------------ missing / null / empty

def test_missing_everything_but_profile():
    ctx = parse_report({"INProfileResponse": {"SCORE": {}}})
    assert ctx["accounts"] == [] and ctx["enquiries"] == []
    assert ctx["score"]["value"] is None and ctx["score"]["display"] == "-"
    assert ctx["applicant"]["name"] == "-"
    assert ctx["header"]["report_date"] == "-"
    assert ctx["summary"]["total"] == "-"


def test_missing_sections_fixture():
    ctx = parse_report(load_fixture("missing_sections"))
    assert ctx["accounts"] == [] and ctx["enquiries"] == []
    assert ctx["score"]["value"] is None
    assert ctx["header"]["report_number"] == "1000000000001"


def test_null_values_render_dash(report):
    a = profile(report)["CAIS_Account"]["CAIS_Account_DETAILS"][0]
    for k in list(a):
        a[k] = None
    acc = parse_report(report)["accounts"][0]
    assert acc["account_type"] == "-" and acc["status"] == "-" and acc["address"] == "-"
    assert acc["history"] == []
    assert acc["phone_rows"] == [[{"type": "-", "number": "-", "ext": "-"}] * 2]
    assert all(v == "-" for _, v in acc["terms"])


def test_empty_arrays(report):
    r = profile(report)
    r["CAIS_Account"]["CAIS_Account_DETAILS"] = []
    r["CAPS"]["CAPS_Application_Details"] = []
    ctx = parse_report(report)
    assert ctx["accounts"] == [] and ctx["enquiries"] == []
    assert ctx["summary"]["total"] == "3"  # summary block still present


def test_single_object_instead_of_array(report):
    r = profile(report)
    one = r["CAIS_Account"]["CAIS_Account_DETAILS"][1]
    one["CAIS_Holder_Details"] = one["CAIS_Holder_Details"][0]
    one["CAIS_Account_History"] = one["CAIS_Account_History"][0]
    r["CAIS_Account"]["CAIS_Account_DETAILS"] = one
    r["Current_Application"]["Current_Application_Details"] = [
        r["Current_Application"]["Current_Application_Details"]]
    ctx = parse_report(report)
    assert len(ctx["accounts"]) == 1
    assert ctx["accounts"][0]["holder_name"] == "TESTFIRST TESTLAST"
    assert len(ctx["accounts"][0]["history"]) == 1
    assert ctx["applicant"]["name"] == "TESTFIRST TESTLAST"


def test_empty_fields_fixture(caplog):
    ctx = parse_report(load_fixture("empty_fields"))
    assert len(ctx["accounts"]) == 2
    assert ctx["accounts"][0]["holder_name"] == "-"
    assert ctx["accounts"][1]["account_type"] == "99"  # unknown code kept raw
    assert ctx["accounts"][1]["current_balance"] == "1398469"
    assert ctx["score"]["value"] is None
    assert "Unknown Account_Type code" in caplog.text


def test_wrong_types_do_not_crash(report):
    r = profile(report)
    r["SCORE"] = "not-a-dict"
    r["CAIS_Account"]["CAIS_Summary"] = []
    r["CAIS_Account"]["CAIS_Account_DETAILS"][0]["CAIS_Account_History"] = "garbage"
    r["CAIS_Account"]["CAIS_Account_DETAILS"][0]["Current_Balance"] = 12345
    r["CAIS_Account"]["CAIS_Account_DETAILS"].append("not an account")
    ctx = parse_report(report)
    assert ctx["score"]["value"] is None
    assert len(ctx["accounts"]) == 3
    assert ctx["accounts"][0]["current_balance"] == "12345"
    assert ctx["summary"]["total"] == "3"  # computed from accounts when summary missing


def test_unknown_codes_fall_back_to_raw(report, caplog):
    profile(report)["CAIS_Account"]["CAIS_Account_DETAILS"][0]["Account_Type"] = "98"
    assert parse_report(report)["accounts"][0]["account_type"] == "98"
    assert "Unknown Account_Type code" in caplog.text


# ------------------------------------------------------------------ input shapes / errors

@pytest.mark.parametrize("shape", ["full", "result_json", "profile", "string", "bytes", "stringified"])
def test_accepted_input_shapes(shape):
    r = profile(DUMMY)
    data = {
        "full": DUMMY,
        "result_json": {"INProfileResponse": r},
        "profile": r,
        "string": json.dumps(DUMMY),
        "bytes": json.dumps(DUMMY).encode(),
        "stringified": {"data": {"result": {"result_json": json.dumps({"INProfileResponse": r})}}},
    }[shape]
    assert find_profile(data)["SCORE"]["BureauScore"] == "742"


@pytest.mark.parametrize("bad", ["{not json", b"\xff\xfe\x00", "[]", "42", {"foo": "bar"}, None])
def test_invalid_input_raises(bad):
    with pytest.raises(InvalidReportError):
        parse_report(bad)


def test_as_list():
    assert as_list(None) == []
    assert as_list({"a": 1}) == [{"a": 1}]
    assert as_list([{"a": 1}, "x", None]) == [{"a": 1}]
    assert as_list("text") == []
