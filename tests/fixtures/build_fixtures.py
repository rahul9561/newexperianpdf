"""Regenerate the test fixtures. All data is synthetic (fake names, PANs, phones, addresses).

    python tests/fixtures/build_fixtures.py

Nothing is copied from input/sample.json; the structure mirrors the Experian
INProfileResponse schema only.
"""

import copy
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent

# Values the tests assert on (see tests/test_output.py).
DUMMY = {
    "first_name": "testfirst",
    "last_name": "testlast",
    "pan": "ABCDE1234F",
    "mobile": "9000000001",
    "score": "742",
    "report_number": "1000000000001",
    "report_date": "20260101",
    "report_time": "101500",
}


def envelope(profile: dict) -> dict:
    """Wrap a profile in the same outer shape the Experian gateway returns."""
    return {
        "data": {
            "result": {"result_json": {"INProfileResponse": profile}},
            "message": "success", "result_code": 101, "http_response_code": 200,
        },
        "status": True,
        "message": "Credit Analytics Success",
        "request_id": "TEST_REQUEST_0001",
        "reference_number": "REFTEST0001",
    }


def history(start_year: int, start_month: int, months: int, dpd=lambda i: "0", ac=lambda i: "?"):
    out, y, m = [], start_year, start_month
    for i in range(months):
        out.append({"Year": str(y), "Month": f"{m:02d}", "Days_Past_Due": dpd(i),
                    "Asset_Classification": ac(i)})
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    return out


def account(n: int, *, acc_type="05", status="11", closed=None, balance="250000", overdue="0",
            limit=None, sanction="500000", months=14, dpd=lambda i: "0", ac=lambda i: "?") -> dict:
    return {
        "Subscriber_Name": f"Test Bank {n % 5 + 1} Ltd",
        "Account_Number": f"XXXXXXXX{1000 + n}",
        "Account_Type": acc_type,
        "Account_Status": status,
        "Portfolio_Type": "I",
        "Open_Date": f"20{10 + n % 15:02d}0{n % 9 + 1}15",
        "Date_Closed": closed,
        "Date_Reported": "20251231" if closed is None else closed,
        "Date_of_Last_Payment": "20251205",
        "CurrencyCode": "INR",
        "Highest_Credit_or_Original_Loan_Amount": sanction,
        "Credit_Limit_Amount": limit,
        "Current_Balance": balance,
        "Amount_Past_Due": overdue,
        "Rate_of_Interest": "11.500",
        "Repayment_Tenure": "36",
        "Value_of_Collateral": None,
        "Type_of_Collateral": None,
        "AccountHoldertypeCode": "1",
        "Occupation_Code": "S",
        "SuitFiled_WilfulDefault": "00",
        "SuitFiledWillfulDefaultWrittenOffStatus": None,
        "Written_off_Settled_Status": None,
        "Written_Off_Amt_Total": None,
        "Written_Off_Amt_Principal": None,
        "Settlement_Amount": None,
        "CAIS_Account_History": history(2025, 12, months, dpd, ac),
        "CAIS_Holder_Details": [{
            "First_Name_Non_Normalized": DUMMY["first_name"].upper(),
            "Middle_Name_1_Non_Normalized": None,
            "Surname_Non_Normalized": DUMMY["last_name"].upper(),
            "Gender_Code": "2",
            "Date_of_birth": "19900115",
            "Income_TAX_PAN": DUMMY["pan"],
        }],
        "CAIS_Holder_ID_Details": [{
            "Income_TAX_PAN": DUMMY["pan"], "PAN_Issue_Date": None, "PAN_Expiration_Date": None,
            "EMailId": "TEST.USER@EXAMPLE.COM", "Passport_Number": None, "Voter_ID_Number": None,
            "Universal_ID_Number": None, "Driver_License_Number": None, "Ration_Card_Number": None,
        }],
        "CAIS_Holder_Phone_Details": [
            {"Telephone_Type": "01", "Mobile_Telephone_Number": DUMMY["mobile"], "Telephone_Number": None,
             "Telephone_Extension": None, "EMailId": "TEST.USER@EXAMPLE.COM"},
            {"Telephone_Type": "03", "Mobile_Telephone_Number": None, "Telephone_Number": "02200000000",
             "Telephone_Extension": "12", "EMailId": None},
        ],
        "CAIS_Holder_Address_Details": [{
            "First_Line_Of_Address_non_normalized": f"FLAT {100 + n} TEST RESIDENCY",
            "Second_Line_Of_Address_non_normalized": "SAMPLE ROAD",
            "Third_Line_Of_Address_non_normalized": None,
            "City_non_normalized": "TESTCITY",
            "State_non_normalized": "27",
            "ZIP_Postal_Code_non_normalized": "400001",
            "CountryCode_non_normalized": "IB",
        }],
    }


def enquiry(i: int) -> dict:
    return {
        "Subscriber_Name": f"Test Finance {i} Private Limited",
        "Date_of_Request": f"202512{i:02d}",
        "ReportNumber": f"20000000{i:05d}",
        "Enquiry_Reason": "13",
        "Amount_Financed": str(100000 * i),
        "Duration_Of_Agreement": "24",
        "CAPS_Applicant_Details": {
            "First_Name": DUMMY["first_name"], "Last_Name": DUMMY["last_name"], "Gender_Code": "2",
            "IncomeTaxPan": DUMMY["pan"], "Date_Of_Birth_Applicant": "19900115",
            "MobilePhoneNumber": DUMMY["mobile"],
        },
        "CAPS_Applicant_Address_Details": {  # single object, not an array
            "FlatNoPlotNoHouseNo": "FLAT 101", "BldgNoSocietyName": "TEST RESIDENCY",
            "RoadNoNameAreaLocality": "SAMPLE ROAD", "City": "TESTCITY", "State": "27", "PINCode": "400001",
        },
    }


def profile(accounts: list, enquiries: list) -> dict:
    active = sum(a["Account_Status"] == "11" for a in accounts)
    return {
        "Header": {"ReportDate": DUMMY["report_date"], "ReportTime": DUMMY["report_time"]},
        "CreditProfileHeader": {"ReportDate": DUMMY["report_date"], "ReportTime": DUMMY["report_time"],
                                "ReportNumber": DUMMY["report_number"], "Version": "V2.4"},
        "SCORE": {"BureauScore": DUMMY["score"], "BureauScoreConfidLevel": None},
        "Current_Application": {"Current_Application_Details": {
            "Enquiry_Reason": "6", "Amount_Financed": "0", "Duration_Of_Agreement": "0",
            "Current_Applicant_Details": {
                "First_Name": DUMMY["first_name"], "Last_Name": DUMMY["last_name"],
                "IncomeTaxPan": DUMMY["pan"], "MobilePhoneNumber": DUMMY["mobile"],
                "EMailId": "test.user@example.com", "Date_Of_Birth_Applicant": "19900115",
            },
        }},
        "CAIS_Account": {
            "CAIS_Summary": {
                "Credit_Account": {
                    "CreditAccountTotal": str(len(accounts)), "CreditAccountActive": str(active),
                    "CreditAccountClosed": str(len(accounts) - active), "CreditAccountDefault": "0",
                    "CADSuitFiledCurrentBalance": "0",
                },
                "Total_Outstanding_Balance": {
                    "Outstanding_Balance_All": "900000", "Outstanding_Balance_Secured": "600000",
                    "Outstanding_Balance_UnSecured": "300000",
                },
            },
            "CAIS_Account_DETAILS": accounts,
        },
        "CAPS": {
            "CAPS_Summary": {"CAPSLast7Days": "0", "CAPSLast30Days": str(min(len(enquiries), 2)),
                             "CAPSLast90Days": str(len(enquiries)), "CAPSLast180Days": str(len(enquiries))},
            "CAPS_Application_Details": enquiries,
        },
        "NonCreditCAPS": {"NonCreditCAPS_Summary": {
            "NonCreditCAPSLast7Days": "0", "NonCreditCAPSLast30Days": "1",
            "NonCreditCAPSLast90Days": "1", "NonCreditCAPSLast180Days": "1"}},
    }


def dummy_report():
    accounts = [
        account(1, acc_type="02", balance="600000", sanction="2500000", months=24),
        account(2, acc_type="10", balance="300000", limit="400000", sanction="150000",
                overdue="4500", dpd=lambda i: "30" if i == 1 else "0"),
        account(3, acc_type="05", status="13", closed="20230630", balance="0", months=6),
    ]
    return envelope(profile(accounts, [enquiry(1), enquiry(2)]))


def many_accounts():
    accounts = []
    for n in range(40):
        a = account(n, acc_type=["05", "10", "02", "07", "34"][n % 5],
                    status="13" if n % 3 == 2 else "11", closed="20240131" if n % 3 == 2 else None,
                    months=36)
        if n % 7 == 3:  # 90+ DPD and asset classification letters
            a["CAIS_Account_History"] = history(
                2025, 12, 12, dpd=lambda i: ["0", "30", "60", "95", "120", None][i % 6],
                ac=lambda i: ["?", "?", "M", "B", "D", "L"][i % 6])
        if n % 11 == 5:
            a["Account_Status"] = "89"  # wilful default
            a["Written_off_Settled_Status"] = "02"
        accounts.append(a)
    return envelope(profile(accounts, [enquiry(i) for i in range(1, 9)]))


def missing_sections():
    return envelope({
        "SCORE": {"BureauScore": None},
        "CreditProfileHeader": {"ReportNumber": DUMMY["report_number"]},
    })


def empty_fields():
    a = account(1)
    for k in list(a):
        if not isinstance(a[k], (list, dict)):
            a[k] = ""
    a["CAIS_Holder_Details"] = []
    a["CAIS_Holder_ID_Details"] = None
    a["CAIS_Holder_Phone_Details"] = {}
    a["CAIS_Holder_Address_Details"] = []
    a["CAIS_Account_History"] = []

    b = account(2)
    b["CAIS_Holder_Details"] = copy.deepcopy(b["CAIS_Holder_Details"][0])  # object instead of array
    b["CAIS_Holder_Details"]["Surname_Non_Normalized"] = (
        "VERYLONGSURNAMEWITHOUTANYSPACESTHATMUSTWRAPINSIDEITSBOXANDNEVEROVERFLOWTHEPAGE TESTLAST")
    b["CAIS_Holder_Address_Details"] = {
        "First_Line_Of_Address_non_normalized": "HOUSE 29 " + "TEST AVENUE SAMPLE NAGAR TESTCITY " * 6,
        "State_non_normalized": "77", "ZIP_Postal_Code_non_normalized": "400001",
    }
    b["Account_Type"] = "99"          # unknown code -> raw code + warning
    b["Current_Balance"] = 1398469    # number instead of string
    b["Extra_Unknown_Field"] = {"nested": [1, 2, 3]}

    p = profile([a, b], [])
    p["CAIS_Account"]["CAIS_Summary"] = None
    p["SCORE"] = {"BureauScore": "0"}
    p["Current_Application"]["Current_Application_Details"]["Current_Applicant_Details"] = {
        "First_Name": None, "Last_Name": "", "IncomeTaxPan": None}
    bad_enquiry = enquiry(1)
    bad_enquiry["CAPS_Applicant_Details"] = None
    p["CAPS"] = {"CAPS_Summary": {}, "CAPS_Application_Details": bad_enquiry}
    return envelope(p)


BUILDERS = {
    "dummy_report": dummy_report,
    "many_accounts": many_accounts,
    "missing_sections": missing_sections,
    "empty_fields": empty_fields,
}


def main():
    for name, builder in BUILDERS.items():
        (HERE / f"{name}.json").write_text(json.dumps(builder(), indent=1), encoding="utf-8")
        print("wrote", name)


if __name__ == "__main__":
    main()
