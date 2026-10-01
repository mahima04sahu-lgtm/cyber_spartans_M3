# Configuration for Abhedya Ingestion & Detection Engine

# Foreign IP prefixes associated with offshore/mule cash-out infrastructure
FOREIGN_IP_PREFIXES = ["185.", "194."]

# Device types considered headless or emulator automation
HEADLESS_DEVICE_TYPES = ["Web_Emulator", "Linux_Script"]

# Narration regex classifiers
NARRATION_CATEGORIES = {
    "crypto_p2p": r"(?i)(crypto|usdt|binance|bybit|p2p exchange|wazirx|coinswitch|bitbns)",
    "wallet": r"(?i)(wallet|topup|paytm|phonepe wallet|gpay wallet|cashfree|razorpay wallet)",
    "atm_cash": r"(?i)(atm|cashout|cash withdrawal|self withdrawal|branch cash)",
    "task_scam": r"(?i)(task|telegram|part time|like review|youtube task|rating scam)",
    "investment_scam": r"(?i)(investment|high yield|guaranteed return|trading profit|fx option|doubling)",
    "loan_app": r"(?i)(loan|quick credit|instant approval|processing fee|repayment)",
    "salary": r"(?i)(salary|payroll|stipend|wages|remuneration)",
    "bill": r"(?i)(bill|utility|electricity|recharge|broadband|water)",
    "normal_transfer": r"(?i)(upi transfer|p2p transfer|immediate fund move|rent payment|grocery)",
}

# Bank IFSC Prefix (first 4 characters) to Bank Name Mapping
BANK_IFSC_MAP = {
    "SBIN": "State Bank of India",
    "HDFC": "HDFC Bank",
    "ICIC": "ICICI Bank",
    "UTIB": "Axis Bank",
    "PUNB": "Punjab National Bank",
    "BARB": "Bank of Baroda",
    "CNRB": "Canara Bank",
    "KKBK": "Kotak Mahindra Bank",
    "IDIB": "Indian Bank",
    "YESB": "Yes Bank",
    "INDB": "IndusInd Bank",
    "UBIN": "Union Bank of India",
}

# Structuring threshold rules (Amounts just under ₹50,000 or ₹1,00,000)
STRUCTURING_RANGES = [
    (48000.0, 49999.99),
    (98000.0, 99999.99),
    (198000.0, 199999.99),
    (498000.0, 499999.99)
]
