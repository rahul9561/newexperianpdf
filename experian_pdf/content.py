"""Fixed wording that appears in every report (not consumer data).

Kept out of the templates so the templates only render context values.
"""

SCORE_INTRO = (
    "Your Experian Credit Report is summarized in the form of Experian Credit Score "
    "which ranges from 300 - 900."
)

SCORE_FACTORS = [
    ("1. Recency", "Recent Credit Account Defaults"),
    ("2. Leverage", "Credit Accounts with on-time re-payment history"),
    ("3. Coverage", "Non-delinquent and delinquent Credit Accounts"),
    ("4. Delinquency Status", "Defaults on Credit Accounts (current & recent periodic intervals)"),
    ("5. Credit Applications", "Credit Account Applications over last 30 days"),
]

SUMMARY_INTRO = (
    "This section displays summary of all your reported credit accounts found in the "
    "Experian Credit Bureau database"
)

ACCOUNTS_INTRO = (
    "This section has information based on the details provided to Experian by all our "
    "member banks, credit / financial institutions and other credit grantors with whom you "
    "have a credit / loan account."
)

ENQUIRIES_INTRO = (
    "This section shows the names of the credit institutions that have processed a "
    "credit / loan application for you."
)

NO_ENQUIRIES = "No credit enquiries reported."

NO_ACCOUNTS = "No credit accounts reported."

NON_CREDIT_INTRO = (
    "This section shows non-credit enquiries such as authentication requests and request "
    "for your Experian Credit Report & Credit Score by you"
)

CONTACT_TEXT = (
    "If you find a discrepancy in your report, it is important to quickly raise it with your "
    "lender.Under the Credit Information Companies (Regulation) Act 2005 and as per the "
    "guidelines set by the Reserve Bank of India, Experian Credit Information Company of India "
    "Private Limited is not authorized to change any data in your credit information report "
    "without authorisation from your lender. However, we would be happy to help you with this "
    "process. If you would like us to help please visit https://consumer.experian.in/ECV-OLN/ "
    "to raise a dispute regarding the discrepancy."
)

# (bold term, description, [(bold sub-term or "", sub-description), ...])
LEGEND = [
    ("SF/WD/WO/SET/RES:", "", [
        ("", "Credit Accounts that are Suit Filed."),
        ("", "Wilful Default."),
        ("", "Written Off."),
        ("", "Settled."),
        ("", "Restructured."),
    ]),
    ("Active*:", " Credit accounts which are less than 90 days past due.", []),
    ("Active**:", " Credit accounts which are over 90 days past due.", []),
    ("Closed:", " Credit accounts that have 'Date Closed' populated.", []),
    ("DPD:", " Days Past Due. Number of days that have passed from the agreed payment due date of EMI.", []),
    ("DPD '0':", " The number '0' in the circle indicates that the Payment is made as agreed and the "
                 "credit account is up to date.", []),
    ("DPD >0:", ' The number in the circle indicates the "Days Past Due" reported by the respective lender.', []),
    ("When the below alphabets are shown in the DPD table, it means the lender is reporting Asset "
     "Classification and indicates the following:", "", [
        ("S:", " Standard. An account which is overdue for less than 90 days is considered a Standard "
               "asset as per RBI guidelines."),
        ("M:", ' Special Mention. These accounts are "Standard" assets but for some discrepancy the '
               "lending organization would like to monitor this account closely."),
        ("B:", " Substandard. An account which is overdue by 90 days for a period of less than or equal "
               "to 12 months is classified as Substandard asset as per RBI guidelines."),
        ("D:", " Doubtful. An account which is overdue by 90 days for more than 12 months is classified "
               "as Doubtful asset as per RBI guidelines."),
        ("L:", " Loss. An account where loss has been identified but the amount has not been written off, "
               "wholly or partially, is classified as Loss asset as per RBI guidelines."),
    ]),
]

END_OF_REPORT = "<---------- END OF REPORT ---------->"

DISCLAIMER = (
    'Experian Credit Information Company of India Private Limited ("ECICI") is registered as a '
    "Credit Information Company with the Reserve Bank of India. ECICI has empanelled several credit "
    'institutions / specified users ("Members") with it, from whom it collects information / data '
    "for the bureau operations. The current Experian Credit Information Report and Experian Credit "
    'Score ("Report") is a reflection of this information / data as submitted by the Member to ECICI. '
    "The Report may thus be limited to the information / data contributed by the Member. The "
    "information / data provided in the Report is as current and up to date as provided by the "
    "Members. The Report is not a guarantee of any particular outcome and you may therefore not use "
    "any information, in full or in part, as the sole basis for any decision you take. ECICI does not "
    "accept any responsibility for any loss that may arise to you from relying on the information / "
    "data in the Report. ECICI will use all reasonable skill and care in the supply of the information "
    "/ data to you. However since we obtain the information / data from the Member, ECICI cannot "
    "guarantee or warranty that the information contained in the Report is complete, accurate, "
    "up-to-date or error-free. Any information contained herein does not reflect the views of ECICI "
    "or its directors or employees. This message contains legally privileged and/or confidential "
    "information. If you are not the intended recipient(s) of this message, you are hereby notified "
    "that any dissemination, distribution or copying of this Report is strictly prohibited. If you "
    "have received this Report in error, please notify the sender immediately and delete this Report "
    "from your computer and all your records."
)
