# Field Mapping — Experian JSON → PDF

Root for all paths below: `data.result.result_json.INProfileResponse` (abbreviated `R`).
Per-account paths are relative to one item of `R.CAIS_Account.CAIS_Account_DETAILS[]` (abbreviated `A`).

> Note: `pdfsample/experiansample.pdf` was generated for a **different consumer** (VISHAL, 4 accounts, 4 enquiry
> blocks) than `input/sample.json` (ARUN, 15 accounts, 0 enquiries). Mapping below is by field/label, not by value.

## Legend for "Format"
- `raw` – printed as-is · `ymd-dash` – `20260531` → `2026-05-31` · `amount` – integer string, no grouping (as sample)
- `-` – any null / empty string / missing key renders as `-`
- `code→label` – lookup table in `formatters.py` (unknown code → raw code + warning log)

## 1. Header (page 1 only in sample)
| PDF label | JSON path | Format | Notes |
|---|---|---|---|
| Logo | `assets/experian_logo.svg` | – | |
| Report Date | `R.CreditProfileHeader.ReportDate` (fallback `R.Header.ReportDate`) | raw `YYYYMMDD` | sample prints unformatted `20260612` |
| Report Time | `R.CreditProfileHeader.ReportTime` (fallback `R.Header.ReportTime`) | raw `HHMMSS` | sample prints `125101` |
| Report Number | `R.CreditProfileHeader.ReportNumber` | raw | |

## 2. Current Application Information
Base `C = R.Current_Application.Current_Application_Details.Current_Applicant_Details`
| PDF label | JSON path | Format |
|---|---|---|
| Name | `C.First_Name`, `C.Middle_Name1..3`, `C.Last_Name` joined | UPPERCASE |
| Mobile Phone | `C.MobilePhoneNumber` (fallback `C.Telephone_Number_Applicant_1st`) | raw |
| Passport Number | `C.Passport_number` | raw |
| Email | `C.EMailId` | raw |
| Date of Birth | `C.Date_Of_Birth_Applicant` | ymd-dash |
| PAN | `C.IncomeTaxPan` | raw |
| Voter ID | `C.Voter_s_Identity_Card` | raw |
| Aadhaar Number | `C.Universal_ID_Number` | raw |
| Ration Card | `C.Ration_Card_Number` | raw |
| Driving License | `C.Driver_License_Number` | raw |

## 3. Experian Credit Score
| PDF element | JSON path | Notes |
|---|---|---|
| Score number (e.g. 627) | `R.SCORE.BureauScore` | missing/non-numeric → `-`, gauge drawn without needle |
| Gauge needle | same | angle = 180° − (score−300)/600 × 180°, clamped 300–900 |
| Gauge bands | – | red 300–500, orange 500–600, yellow 600–700, light-green 700–900 (measured from sample vectors) |
| "Score Factors" 1–5 text | **NOT IN JSON** | static text in sample; kept as template constants |
| Orange intro sentence | **NOT IN JSON** | static text |

## 4. Report Summary
| PDF label | JSON path |
|---|---|
| Total number of Accounts | `R.CAIS_Account.CAIS_Summary.Credit_Account.CreditAccountTotal` |
| Active Accounts | `…Credit_Account.CreditAccountActive` |
| Closed Accounts | `…Credit_Account.CreditAccountClosed` |
| SF/WD/WO/SET/RES | `…Credit_Account.CreditAccountDefault` |
| Total Current Bal. amt | `R.CAIS_Account.CAIS_Summary.Total_Outstanding_Balance.Outstanding_Balance_All` |
| SF/WD/WO/Settled amt | `…Credit_Account.CADSuitFiledCurrentBalance` (sample shows blank) |
| Secured Accounts amt | `…Total_Outstanding_Balance.Outstanding_Balance_Secured` |
| Unsecured Accounts amt | `…Total_Outstanding_Balance.Outstanding_Balance_UnSecured` |
| Last 7/30/90/180 days credit enquiries | `R.CAPS.CAPS_Summary.CAPSLast7Days / 30 / 90 / 180` |
| Last 7/30/90/180 days non-credit enquiries | `R.NonCreditCAPS.NonCreditCAPS_Summary.NonCreditCAPSLast7Days / …` |

If the summary block is missing, counts fall back to values computed from the account list.

## 5. Summary table (one row per account)
| Column | JSON path | Format |
|---|---|---|
| Sr.no | index → `Acc1`, `Acc2`… | – |
| Account Type | `A.Account_Type` | code→label (Experian India account-type table, e.g. `10`→`CREDIT CARD`) |
| Account No | `A.Account_Number` | raw (already masked by bureau) |
| Date Reported | `A.Date_Reported` | ymd-dash |
| Account Status | `A.Account_Status` | code→`ACTIVE`/`CLOSED`/SF-WD-WO label (`11`→ACTIVE, `12`,`13`→CLOSED) |
| Date Opened | `A.Open_Date` | ymd-dash |
| Currency code | `A.CurrencyCode` | raw |
| Sanction Amt / Highest Credit | `A.Highest_Credit_or_Original_Loan_Amount` | amount |
| Current Balance | `A.Current_Balance` | amount |
| Overdue Amount | `A.Amount_Past_Due` | amount |

## 6. Credit Account Information Details (repeated per account)
### 6a. Account header card
| PDF element | JSON path | Notes |
|---|---|---|
| Name (bold blue) | `A.CAIS_Holder_Details[0]`: `First_Name_Non_Normalized`, `Middle_Name_1..3_Non_Normalized`, `Surname_Non_Normalized` joined | |
| Address | `A.CAIS_Holder_Address_Details[0]`: lines 1–5, `City_non_normalized`, state (code→name), `ZIP_Postal_Code_non_normalized` joined by spaces | first address only, as sample |
| Acct :N | index | |

### 6b. Credit Account details (3 columns)
| PDF label | JSON path | Format |
|---|---|---|
| Account Number | `A.Account_Number` | raw |
| Date Opened | `A.Open_Date` | ymd-dash |
| Date Closed | `A.Date_Closed` | ymd-dash |
| Ownership | `A.AccountHoldertypeCode` | code→label (1 Individual, 2 Joint, 3 Authorised User, 7 Guarantor). **Sample shows `-`** |
| Rate of Interest | `A.Rate_of_Interest` | number, trailing zeros trimmed |
| Value of Collateral | `A.Value_of_Collateral` | amount |
| Type of Collateral | `A.Type_of_Collateral` | raw |
| SuitFiled Willful Default WrittenOff Status | `A.SuitFiledWillfulDefaultWrittenOffStatus` | raw |
| Date Reported | `A.Date_Reported` | ymd-dash |
| Loan Type | `A.Account_Type` | code→label. **Sample shows `-`** (see open questions) |
| Account Status | `A.Account_Status` | code→label |
| Current Balance | `A.Current_Balance` | amount |
| Amount Overdue | `A.Amount_Past_Due` | amount |
| Last Payment Date | `A.Date_of_Last_Payment` | ymd-dash |
| SuitFiled Willful Default | `A.SuitFiled_WilfulDefault` | code→label (00 No Suit Filed, 01 Suit Filed, 02 Wilful Default, 03 Suit Filed (Wilful Default)) |
| Credit Limit Amt | `A.Credit_Limit_Amount` | amount |
| Repayment Tenure | `A.Repayment_Tenure` | raw |
| Total Write-off Amt | `A.Written_Off_Amt_Total` | amount |
| Principal Write-off | `A.Written_Off_Amt_Principal` | amount |
| Settlement Amt | `A.Settlement_Amount` | amount |
| Written off Settled Status | `A.Written_off_Settled_Status` | raw code (sample prints `99`) |

### 6c. Payment History grid
| Element | JSON path | Notes |
|---|---|---|
| Year rows (desc) × Jan–Dec | `A.CAIS_Account_History[].Year`, `.Month` | |
| Circle value | `.Days_Past_Due`; if empty and `.Asset_Classification` is a letter (S/M/B/D/L) → the letter | |
| Circle colour | derived | 0 → green `#2e9e4c`; 1–89 → orange `#fa7524`; ≥90 or B/D/L → red |
| (`Payment_History_Profile` string) | not used | the monthly history array is authoritative |

### 6d. Consumer Personal details on the Credit Account
| PDF label | JSON path | Format |
|---|---|---|
| Date of Birth | `A.CAIS_Holder_Details[0].Date_of_birth` | ymd-dash |
| Gender | `A.CAIS_Holder_Details[0].Gender_Code` | 1 Male, 2 Female, 3 Transgender |
| Occupation | `A.Occupation_Code` | S Salaried, N Non-Salaried, E Self Employed, P Self Employed Professional, U Unemployed |
| Email Address | first non-empty `EMailId` in `A.CAIS_Holder_ID_Details[]` then `A.CAIS_Holder_Phone_Details[]` | |
| Phone Type / Number / Extension (2 per row) | `A.CAIS_Holder_Phone_Details[]`: `Telephone_Type` (leading zeros stripped, as sample), `Mobile_Telephone_Number` or `Telephone_Number`, `Telephone_Extension` | de-duplicated |
| PAN / Passport / Voter ID / Aadhaar-UID / Driving License / Ration Card, with Date of Issue / Expiry | `A.CAIS_Holder_ID_Details[]` (first non-empty per type): `Income_TAX_PAN`+`PAN_Issue_Date`/`PAN_Expiration_Date`, `Passport_Number`…, `Voter_ID_Number`…, `Universal_ID_Number`…, `Driver_License_Number`…, `Ration_Card_Number`…; falls back to `CAIS_Holder_Details[].Income_TAX_PAN` etc. | dates ymd-dash |

## 7. Credit Enquiries (one block per enquiry)
Source: `R.CAPS.CAPS_Application_Details[]` (**absent in sample.json**: this JSON has no enquiries).
| PDF label | JSON path (standard Experian CAPS schema) |
|---|---|
| Name | `CAPS_Applicant_Details.First_Name` + `Middle_Name1..3` + `Last_Name` |
| Address | `CAPS_Applicant_Address_Details`: `FlatNoPlotNoHouseNo`, `BldgNoSocietyName`, `RoadNoNameAreaLocality`, `City`, `Landmark`, `State`, `PINCode` |
| Date of Birth | `CAPS_Applicant_Details.Date_Of_Birth_Applicant` |
| Telephone | `CAPS_Applicant_Details.Telephone_Number_Applicant_1st` |
| Mobile Phone | `CAPS_Applicant_Details.MobilePhoneNumber` |
| Gender | `CAPS_Applicant_Details.Gender_Code` |
| PAN / Passport Number / Voter ID / Driving License / Ration Card | `IncomeTaxPan` / `Passport_number` / `Voter_s_Identity_Card` / `Driver_License_Number` / `Ration_Card_Number` |
| ERN | `ReportNumber` |
| Search Type | `Enquiry_Reason` (raw code; the Experian enquiry-reason table was not available to verify labels) |
| Credit Institution Name | `Subscriber_Name` |
| Application Date | `Date_of_Request` |
| Amount Applied For | `Amount_Financed` |
| Duration of Agreement | `Duration_Of_Agreement` |

**Discrepancy found:** in the sample PDF the 4 "Cr Enq" blocks repeat the names, addresses and phones of accounts 1–4,
while ERN / Search Type / Institution are all `-` and the CAPS summary says 0 enquiries. The sample generator appears
to have filled this section from account-holder data. This engine uses the real CAPS enquiry data (see open questions).

## 8. Non-Credit Enquiries, Contacting Us, Legend, End of Report, Disclaimer
Static text only. **NOT IN JSON.** Kept in `experian_pdf/content.py` (not in templates).

## JSON fields not shown in the sample PDF
`R.SCORE.BureauScoreConfidLevel`, `R.Match_result.Exact_match`, `R.TotalCAPS_Summary.*`, `R.UserMessage`,
`R.CreditProfileHeader.Version/StageOneId/Subscriber_Name`, `A.Portfolio_Type`, `A.Terms_Duration`, `A.Terms_Frequency`,
`A.Income*`, `A.Scheduled_Monthly_Payment_Amount`, `A.Identification_Number`, `A.DateOfAddition`,
`A.Payment_History_Profile`, `A.Date_of_First_Delinquency`, `A.Special_Comment`, `A.*_comments`, `Current_Other_Details.*`,
`Current_Applicant_Address_Details`, top-level `request_id`, `reference_number`.

## Items in the PDF not found in the JSON
1. Score Factors 1–5 and the score intro sentence: static.
2. Section description sentences (orange), Contacting Us, Legend, END OF REPORT, disclaimer: static.
3. Credit Enquiry detail blocks: `CAPS_Application_Details` absent from this sample JSON.
4. Aadhaar Number (application): `Universal_ID_Number` is null in this JSON; renders `-`.

## Code tables
Code→label tables live in `experian_pdf/codes.py` and follow the Experian India CAIS code manual (account type,
account status, ownership, SuitFiled/Wilful default, gender, occupation, state). Verify them against your Experian
contract documentation. Unknown codes print the raw code and log a warning, so nothing is silently dropped.
