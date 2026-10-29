"""Turn a raw Experian API response into a flat, display-ready context dict.

All parsing and formatting decisions live here; templates only print strings.
The parser never raises on missing/extra/malformed keys (it logs a warning and
falls back to "-"). It raises ``InvalidReportError`` only when the input is not
JSON or has no ``INProfileResponse`` at all.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from . import codes
from . import formatters as fmt
from .exceptions import InvalidReportError
from .gauge import SCORE_MAX, SCORE_MIN

logger = logging.getLogger(__name__)

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
ASSET_CLASS_LETTERS = {"S", "M", "B", "D", "L"}
ID_TYPES = [
    # label, number key, issue date key, expiry date key, fallback key on CAIS_Holder_Details
    ("PAN", "Income_TAX_PAN", "PAN_Issue_Date", "PAN_Expiration_Date", "Income_TAX_PAN"),
    ("Passport", "Passport_Number", "Passport_Issue_Date", "Passport_Expiration_Date", "Passport_Number"),
    ("Voter ID", "Voter_ID_Number", "Voter_ID_Issue_Date", "Voter_ID_Expiration_Date", "Voter_ID_Number"),
    ("Aadhaar/UID", "Universal_ID_Number", "Universal_ID_Issue_Date", "Universal_ID_Expiration_Date", None),
    ("Driving License", "Driver_License_Number", "Driver_License_Issue_Date",
     "Driver_License_Expiration_Date", None),
    ("Ration Card", "Ration_Card_Number", "Ration_Card_Issue_Date", "Ration_Card_Expiration_Date", None),
]
ADDRESS_LINE_KEYS = [
    "First_Line_Of_Address_non_normalized",
    "Second_Line_Of_Address_non_normalized",
    "Third_Line_Of_Address_non_normalized",
    "Fourth_Line_Of_Address_non_normalized",
    "Fifth_Line_Of_Address_non_normalized",
]
NO_LENDER = "N/A"


# --------------------------------------------------------------------------- helpers

def _get(obj: Any, *path: str, default: Any = None) -> Any:
    """Safe nested lookup. A list met on the way is treated as its first element."""
    cur = obj
    for key in path:
        if isinstance(cur, list):
            cur = cur[0] if cur else None
        if not isinstance(cur, dict):
            return default
        cur = cur.get(key)
        if cur is None:
            return default
    return cur


def _dict(obj: Any, *path: str) -> dict:
    """Like ``_get`` but always returns a dict (first element of a list, ``{}`` otherwise)."""
    value = _get(obj, *path)
    if isinstance(value, list):
        value = value[0] if value else None
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[dict]:
    """None -> [], dict -> [dict], list -> its dict items."""
    if value is None:
        return []
    if isinstance(value, dict):
        return [value]
    if isinstance(value, list):
        return [v for v in value if isinstance(v, dict)]
    logger.warning("Expected object or array, got %s", type(value).__name__)
    return []


def _first(items: list[dict], key: str) -> Any:
    for item in items:
        if not fmt.is_empty(item.get(key)):
            return item.get(key)
    return None


def _full_name(*parts: Any) -> str:
    name = fmt.join_nonempty(parts)
    return " ".join(name.split())


# --------------------------------------------------------------------------- input

def load_json(source: Any) -> Any:
    if isinstance(source, (bytes, bytearray)):
        try:
            source = source.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise InvalidReportError(f"Input is not UTF-8 text: {exc}") from exc
    if isinstance(source, str):
        try:
            return json.loads(source)
        except json.JSONDecodeError as exc:
            raise InvalidReportError(f"Input is not valid JSON: {exc}") from exc
    return source


def find_profile(data: Any) -> dict:
    """Locate ``INProfileResponse`` in a full API response, a ``result_json`` or the profile itself."""
    data = load_json(data)
    if not isinstance(data, dict):
        raise InvalidReportError(f"Expected a JSON object, got {type(data).__name__}")

    candidates = [
        data,
        _get(data, "data", "result", "result_json"),
        _get(data, "result", "result_json"),
        _get(data, "result_json"),
        _get(data, "data"),
    ]
    for cand in candidates:
        if isinstance(cand, str):  # some gateways stringify result_json
            try:
                cand = json.loads(cand)
            except json.JSONDecodeError:
                continue
        if isinstance(cand, list):
            cand = cand[0] if cand else None
        if not isinstance(cand, dict):
            continue
        profile = cand.get("INProfileResponse")
        if isinstance(profile, list):
            profile = profile[0] if profile else None
        if isinstance(profile, dict):
            return profile
        if any(k in cand for k in ("CAIS_Account", "SCORE", "CreditProfileHeader")):
            return cand
    raise InvalidReportError("No 'INProfileResponse' found in input")


# --------------------------------------------------------------------------- sections

def _header(r: dict) -> dict:
    cph = _dict(r, "CreditProfileHeader")
    hdr = _dict(r, "Header")
    return {
        "report_date": fmt.text(_get(cph, "ReportDate") or _get(hdr, "ReportDate")),
        "report_time": fmt.text(_get(cph, "ReportTime") or _get(hdr, "ReportTime")),
        "report_number": fmt.text(_get(cph, "ReportNumber")),
    }


def _applicant(r: dict) -> dict:
    c = _dict(r, "Current_Application", "Current_Application_Details", "Current_Applicant_Details")
    return {
        "name": _full_name(c.get("First_Name"), c.get("Middle_Name1"), c.get("Middle_Name2"),
                           c.get("Middle_Name3"), c.get("Last_Name")).upper(),
        "mobile": fmt.text(c.get("MobilePhoneNumber") or c.get("Telephone_Number_Applicant_1st")),
        "passport": fmt.text(c.get("Passport_number")),
        "email": fmt.text(c.get("EMailId")),
        "dob": fmt.date_ymd(c.get("Date_Of_Birth_Applicant")),
        "pan": fmt.upper(c.get("IncomeTaxPan")),
        "voter_id": fmt.text(c.get("Voter_s_Identity_Card")),
        "aadhaar": fmt.text(c.get("Universal_ID_Number")),
        "ration_card": fmt.text(c.get("Ration_Card_Number")),
        "driving_license": fmt.text(c.get("Driver_License_Number")),
    }


def _score(r: dict) -> dict:
    raw = _get(r, "SCORE", "BureauScore")
    value = fmt.to_int(raw)
    if value is None or value <= 0:
        if raw is not None:
            logger.warning("No usable bureau score (%r)", raw)
        return {"value": None, "display": fmt.DASH}
    if not SCORE_MIN <= value <= SCORE_MAX:
        logger.warning("Bureau score %s outside %s-%s; needle clamped", value, SCORE_MIN, SCORE_MAX)
    return {"value": value, "display": str(value)}


def _report_summary(r: dict, accounts: list[dict]) -> dict:
    ca = _dict(r, "CAIS_Account", "CAIS_Summary", "Credit_Account")
    ob = _dict(r, "CAIS_Account", "CAIS_Summary", "Total_Outstanding_Balance")
    caps = _dict(r, "CAPS", "CAPS_Summary")
    ncaps = _dict(r, "NonCreditCAPS", "NonCreditCAPS_Summary")

    def count_or(key, computed):
        v = ca.get(key)
        return fmt.amount(v) if not fmt.is_empty(v) else (str(computed) if accounts or ca else fmt.DASH)

    return {
        "total": count_or("CreditAccountTotal", len(accounts)),
        "active": count_or("CreditAccountActive", sum(a["is_active"] for a in accounts)),
        "closed": count_or("CreditAccountClosed", sum(a["is_closed"] for a in accounts)),
        "default": count_or("CreditAccountDefault",
                            sum(not a["is_active"] and not a["is_closed"] for a in accounts)),
        "balance_all": fmt.amount(ob.get("Outstanding_Balance_All")),
        "balance_sf": fmt.amount(ca.get("CADSuitFiledCurrentBalance")),
        "balance_secured": fmt.amount(ob.get("Outstanding_Balance_Secured")),
        "balance_unsecured": fmt.amount(ob.get("Outstanding_Balance_UnSecured")),
        "caps": [fmt.amount(caps.get(f"CAPSLast{d}Days")) for d in (7, 30, 90, 180)],
        "non_caps": [fmt.amount(ncaps.get(f"NonCreditCAPSLast{d}Days")) for d in (7, 30, 90, 180)],
    }


def _account_status(code: Any) -> tuple[str, bool, bool]:
    s = fmt.text(code, "")
    if not s:
        return fmt.DASH, False, False
    key = s.zfill(2) if s.isdigit() else s
    if key in codes.ACCOUNT_STATUS_ACTIVE:
        return "ACTIVE", True, False
    if key in codes.ACCOUNT_STATUS_CLOSED:
        return "CLOSED", False, True
    return fmt.code_label(key, codes.ACCOUNT_STATUS, "Account_Status"), False, False


def _address(addresses: list[dict]) -> str:
    for a in addresses:
        lines = [a.get(k) for k in ADDRESS_LINE_KEYS]
        if all(fmt.is_empty(x) for x in lines):
            continue
        text = fmt.join_nonempty(lines)
        state_code = a.get("State_non_normalized")
        state = None if fmt.is_empty(state_code) else fmt.code_label(state_code, codes.STATE, "State")
        # bureaus often repeat city/PIN inside the free-text lines; don't print them twice
        for extra in (a.get("City_non_normalized"), state, a.get("ZIP_Postal_Code_non_normalized")):
            extra = fmt.text(extra, "")
            if extra and extra.upper() not in text.upper():
                text = f"{text} {extra}"
        return text
    return fmt.DASH


def _dpd_cell(entry: dict) -> dict | None:
    dpd = fmt.text(entry.get("Days_Past_Due"), "")
    ac = fmt.text(entry.get("Asset_Classification"), "").upper()
    if dpd.isdigit():
        days = int(dpd)
        cls = "ok" if days == 0 else ("late" if days < 90 else "bad")
        return {"value": str(days), "cls": cls}
    if ac in ASSET_CLASS_LETTERS:
        cls = {"S": "ok", "M": "late"}.get(ac, "bad")
        return {"value": ac, "cls": cls}
    return None


def _payment_history(history: list[dict]) -> list[dict]:
    years: dict[int, list] = {}
    for entry in history:
        year = fmt.to_int(entry.get("Year"))
        month = fmt.to_int(entry.get("Month"))
        if year is None or month is None or not 1 <= month <= 12:
            logger.warning("Skipping payment history entry with bad Year/Month: %r", entry)
            continue
        row = years.setdefault(year, [None] * 12)
        if row[month - 1] is None:
            row[month - 1] = _dpd_cell(entry)
    return [{"year": str(y), "cells": years[y]} for y in sorted(years, reverse=True)]


def _phones(items: list[dict]) -> list[list[dict]]:
    seen, phones = set(), []
    for p in items:
        number = fmt.text(p.get("Mobile_Telephone_Number") or p.get("Telephone_Number"))
        ptype = fmt.strip_zeros(p.get("Telephone_Type"))
        ext = fmt.text(p.get("Telephone_Extension"))
        if number == fmt.DASH and ptype == fmt.DASH:
            continue
        key = (ptype, number, ext)
        if key in seen:
            continue
        seen.add(key)
        phones.append({"type": ptype, "number": number, "ext": ext})
    blank = {"type": fmt.DASH, "number": fmt.DASH, "ext": fmt.DASH}
    if not phones:
        return [[blank, blank]]
    rows = [phones[i:i + 2] for i in range(0, len(phones), 2)]
    if len(rows[-1]) == 1:
        rows[-1].append(blank)
    return rows


def _ids(id_items: list[dict], holders: list[dict]) -> list[dict]:
    rows = []
    for label, num_key, issue_key, exp_key, fallback_key in ID_TYPES:
        src = next((i for i in id_items if not fmt.is_empty(i.get(num_key))), None)
        if src is not None:
            number, issue, expiry = src.get(num_key), src.get(issue_key), src.get(exp_key)
        else:
            number = _first(holders, fallback_key) if fallback_key else None
            issue = expiry = None
        rows.append({
            "type": label,
            "number": fmt.text(number),
            "issue": fmt.date_ymd(issue),
            "expiry": fmt.date_ymd(expiry),
        })
    return rows


def _lender_name(value: Any) -> str:
    """Subscriber_Name with runs of whitespace collapsed; empty -> ``N/A``."""
    return " ".join(fmt.text(value, "").split()) or NO_LENDER


def _sanction(a: dict) -> Any:
    sanction = a.get("Highest_Credit_or_Original_Loan_Amount")
    return a.get("Credit_Limit_Amount") if fmt.is_empty(sanction) else sanction


def _lender_summary(raw_accounts: list[dict]) -> list[dict]:
    """One row per lender: account counts and summed balance / sanction, most accounts first."""
    groups: dict[str, dict] = {}
    for a in raw_accounts:
        g = groups.setdefault(_lender_name(a.get("Subscriber_Name")), {
            "total": 0, "active": 0, "closed": 0, "balance": [], "sanction": []})
        g["total"] += 1
        g["active"] += fmt.text(a.get("Account_Status"), "").zfill(2) == "11"
        g["closed"] += not fmt.is_empty(a.get("Date_Closed"))
        g["balance"].append(fmt.to_decimal(a.get("Current_Balance")))
        g["sanction"].append(fmt.to_decimal(_sanction(a)))

    def total(values):
        values = [v for v in values if v is not None]
        return fmt.amount(sum(values)) if values else fmt.DASH

    rows = [{"lender": name, "total": str(g["total"]), "active": str(g["active"]),
             "closed": str(g["closed"]), "current_balance": total(g["balance"]),
             "sanction": total(g["sanction"])}
            for name, g in groups.items()]
    rows.sort(key=lambda row: -int(row["total"]))  # stable: ties keep report order
    return rows


def _account(a: dict, index: int) -> dict:
    holders = as_list(a.get("CAIS_Holder_Details"))
    id_items = as_list(a.get("CAIS_Holder_ID_Details"))
    phone_items = as_list(a.get("CAIS_Holder_Phone_Details"))
    holder = next((h for h in holders if any(
        not fmt.is_empty(h.get(k)) for k in ("First_Name_Non_Normalized", "Surname_Non_Normalized"))), {})

    holder_name = _full_name(
        holder.get("First_Name_Non_Normalized"), holder.get("Middle_Name_1_Non_Normalized"),
        holder.get("Middle_Name_2_Non_Normalized"), holder.get("Middle_Name_3_Non_Normalized"),
        holder.get("Surname_Non_Normalized"))
    lender_name = _lender_name(a.get("Subscriber_Name"))
    address = _address(as_list(a.get("CAIS_Holder_Address_Details")))
    status, is_active, is_closed = _account_status(a.get("Account_Status"))
    acc_type = fmt.code_label(a.get("Account_Type"), codes.ACCOUNT_TYPE, "Account_Type")
    sanction = _sanction(a)
    date_reported = fmt.date_ymd(a.get("Date_Reported"))
    account_number = fmt.text(a.get("Account_Number"))
    current_balance = fmt.amount(a.get("Current_Balance"))
    overdue = fmt.amount(a.get("Amount_Past_Due"))

    return {
        "index": index,
        "sr": f"Acc{index}",
        "lender_name": lender_name,
        "holder_name": holder_name,
        "address": address,
        "is_active": is_active,
        "is_closed": is_closed,
        # summary table
        "account_type": acc_type,
        "account_number": account_number,
        "date_reported": date_reported,
        "status": status,
        "date_opened": fmt.date_ymd(a.get("Open_Date")),
        "currency": fmt.text(a.get("CurrencyCode")),
        "sanction": fmt.amount(sanction),
        "current_balance": current_balance,
        "overdue": overdue,
        # detail cards: (icon, label, value) rows
        "holder_rows": [
            ("person", "Name", holder_name),
            ("calendar", "Date of Birth", fmt.date_ymd(_first(holders, "Date_of_birth"))),
            ("gender", "Gender", fmt.code_label(_first(holders, "Gender_Code"), codes.GENDER, "Gender_Code")),
            ("work", "Occupation", fmt.code_label(a.get("Occupation_Code"), codes.OCCUPATION, "Occupation_Code",
                                                  fallback_raw=False)),
            ("mail", "Email Address", fmt.text(_first(id_items, "EMailId") or _first(phone_items, "EMailId"))),
        ],
        "lender_rows": [
            ("bank", "Lender", lender_name),
            ("pin", "Reported Address", address),
        ],
        "terms": [
            ("hash", "Account Number", account_number),
            ("calendar", "Date Opened", fmt.date_ymd(a.get("Open_Date"))),
            ("calendar", "Date Closed", fmt.date_ymd(a.get("Date_Closed"))),
            ("users", "Ownership", fmt.code_label(a.get("AccountHoldertypeCode"), codes.OWNERSHIP, "Ownership")),
            ("percent", "Rate of Interest", fmt.rate(a.get("Rate_of_Interest"))),
        ],
        "description": [
            ("calendar", "Date Reported", date_reported),
            ("file", "Loan Type", acc_type),
            ("status", "Account Status", status),
            ("amount", "Current Balance", current_balance),
            ("alert", "Amount Overdue", overdue),
            ("calendar", "Last Payment Date", fmt.date_ymd(a.get("Date_of_Last_Payment"))),
            ("alert", "SuitFiled Willful Default",
             fmt.code_label(a.get("SuitFiled_WilfulDefault"), codes.SUIT_FILED_WILFUL_DEFAULT,
                            "SuitFiled_WilfulDefault")),
        ],
        "details": [
            ("amount", "Credit Limit Amt", fmt.amount(a.get("Credit_Limit_Amount"))),
            ("clock", "Repayment Tenure", fmt.strip_zeros(a.get("Repayment_Tenure"))),
            ("alert", "Total Write-off Amt", fmt.amount(a.get("Written_Off_Amt_Total"))),
            ("alert", "Principal Write-off", fmt.amount(a.get("Written_Off_Amt_Principal"))),
            ("amount", "Settlement Amt", fmt.amount(a.get("Settlement_Amount"))),
            ("info", "Written off Settled Status", fmt.text(a.get("Written_off_Settled_Status"))),
        ],
        "history": _payment_history(as_list(a.get("CAIS_Account_History"))),
        "phone_rows": _phones(phone_items),
        "ids": _ids(id_items, holders),
    }


def _enquiry(e: dict, index: int) -> dict:
    ap = _dict(e, "CAPS_Applicant_Details")
    addr = (as_list(e.get("CAPS_Applicant_Address_Details")) or [{}])[0]
    address = fmt.join_nonempty([
        addr.get("FlatNoPlotNoHouseNo"), addr.get("BldgNoSocietyName"), addr.get("RoadNoNameAreaLocality"),
        addr.get("City"), addr.get("Landmark"),
        None if fmt.is_empty(addr.get("State")) else fmt.code_label(addr.get("State"), codes.STATE, "State"),
        addr.get("PINCode"),
    ])
    return {
        "index": index,
        "name": _full_name(ap.get("First_Name"), ap.get("Middle_Name1"), ap.get("Middle_Name2"),
                           ap.get("Middle_Name3"), ap.get("Last_Name")).upper(),
        "address": address,
        "col1": [
            ("Date of Birth", fmt.date_ymd(ap.get("Date_Of_Birth_Applicant"))),
            ("Telephone", fmt.text(ap.get("Telephone_Number_Applicant_1st"))),
            ("Mobile Phone", fmt.text(ap.get("MobilePhoneNumber"))),
            ("Gender", fmt.code_label(ap.get("Gender_Code"), codes.GENDER, "Gender_Code")),
        ],
        "col2": [
            ("PAN", fmt.upper(ap.get("IncomeTaxPan"))),
            ("Passport Number", fmt.text(ap.get("Passport_number"))),
            ("Voter ID", fmt.text(ap.get("Voter_s_Identity_Card"))),
            ("Driving License", fmt.text(ap.get("Driver_License_Number"))),
            ("Ration Card", fmt.text(ap.get("Ration_Card_Number"))),
        ],
        "col3": [
            ("ERN", fmt.text(e.get("ReportNumber"))),
            ("Search Type", fmt.text(e.get("Enquiry_Reason"))),
            ("Credit Institution Name", fmt.text(e.get("Subscriber_Name"))),
            ("Application Date", fmt.date_ymd(e.get("Date_of_Request"))),
            ("Amount Applied For", fmt.amount(e.get("Amount_Financed"))),
            ("Duration of Agreement", fmt.strip_zeros(e.get("Duration_Of_Agreement"))),
        ],
    }


# --------------------------------------------------------------------------- public

def parse_report(data: Any) -> dict:
    """Return the template context for one report."""
    r = find_profile(data)

    accounts, parsed_raw = [], []
    raw_accounts = as_list(_get(r, "CAIS_Account", "CAIS_Account_DETAILS"))
    for i, a in enumerate(raw_accounts, start=1):
        try:
            accounts.append(_account(a, len(accounts) + 1))
            parsed_raw.append(a)
        except Exception:  # never let one bad account kill the report
            logger.exception("Skipping account #%s: could not parse", i)

    enquiries = []
    for i, e in enumerate(as_list(_get(r, "CAPS", "CAPS_Application_Details")), start=1):
        try:
            enquiries.append(_enquiry(e, len(enquiries) + 1))
        except Exception:
            logger.exception("Skipping enquiry #%s: could not parse", i)

    return {
        "header": _header(r),
        "applicant": _applicant(r),
        "score": _score(r),
        "summary": _report_summary(r, accounts),
        "accounts": accounts,
        "lenders": _lender_summary(parsed_raw),
        "enquiries": enquiries,
        "months": MONTHS,
    }
