"""
backend/generate_dummy_drive_files.py

Generates a large, deliberately messy set of dummy company files for
Precision Textile Industry Ltd (PTIL) across all six department folders in
backend/seed_docs/ — Excel workbooks (multi-sheet, P&L, order releases, cash
books, inventories), Word documents (letters, reports), and PDFs (invoice,
LC copy). These are the files meant to be uploaded into the real Google
Drive folders for the showcase.

The existing .md policy documents in seed_docs/ are left in place — this
script only adds new files alongside them.

Usage:
    python backend/generate_dummy_drive_files.py
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
from docx import Document
from docx.shared import Pt
from fpdf import FPDF

random.seed(42)

HERE = Path(__file__).resolve().parent
SEED_DIR = HERE / "seed_docs"

FINANCE_DIR = SEED_DIR / "Md. Mizanur Rahman (PTIL)"
COMMERCIAL_DIR = SEED_DIR / "Md. Alamin (Commercial)"
ADMIN_DIR = SEED_DIR / "Riaz Uddin Sarker (Admin)"
MAINTENANCE_DIR = SEED_DIR / "Khorshed Alam Babu (Maintenance)"
HR_DIR = SEED_DIR / "Md. Mozammel Haque (HR)"
ACCOUNTING_DIR = SEED_DIR / "Zahedul Islam Nizam (Accounting)"

for d in (FINANCE_DIR, COMMERCIAL_DIR, ADMIN_DIR, MAINTENANCE_DIR, HR_DIR, ACCOUNTING_DIR):
    d.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Shared gibberish pools
# ---------------------------------------------------------------------------
FIRST_NAMES = [
    "Rafiqul", "Mahmuda", "Shahin", "Nasrin", "Kamal", "Farida", "Habibur",
    "Rehana", "Anwar", "Shirin", "Delwar", "Rokeya", "Mizanur", "Salma",
    "Jahangir", "Nasima", "Aminul", "Rashida", "Golam", "Sultana",
]
LAST_NAMES = [
    "Islam", "Rahman", "Hossain", "Ahmed", "Akter", "Chowdhury", "Karim",
    "Sarker", "Miah", "Begum", "Uddin", "Haque",
]

def rand_name() -> str:
    return f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"

VENDORS = [
    "DESCO Power Ltd.", "Karim Yarn Traders", "Dhaka Dyes & Chemicals",
    "Bengal Freight Forwarders", "Rahman Spare Parts", "Green Textile Accessories",
    "Apex Logistics BD", "Sonar Bangla Packaging", "United Fire Safety Co.",
    "Gazipur Generator Services",
]
CUSTOMERS = [
    "NordicWear AB", "Heritage Apparel Inc.", "Continental Fashion GmbH",
    "Meridian Retail Group", "Northgate Garments Ltd.", "Alpine Textiles Co.",
    "Westbrook Clothing", "Solstice Sportswear",
]
FINANCE_CATEGORIES = [
    "Utilities", "Raw Materials", "Logistics", "LC Charges", "Maintenance",
    "Salary Disbursement", "Office Supplies", "Bank Charges",
]
CURRENCIES = ["BDT", "BDT", "BDT", "USD"]

BASE_DATE = datetime(2026, 8, 1)

def rand_date(days_span: int = 55) -> datetime:
    return BASE_DATE + timedelta(days=random.randint(0, days_span))

def fmt_date(d: datetime, style: int) -> str:
    # deliberately inconsistent formatting across rows, like a real messy sheet
    if style == 0:
        return d.strftime("%Y-%m-%d")
    if style == 1:
        return d.strftime("%d/%m/%Y")
    return d.strftime("%d-%b-%Y")


# ---------------------------------------------------------------------------
# Finance: Cash Book (multi-sheet, messy)
# ---------------------------------------------------------------------------
def build_cash_book():
    sheets = {}
    for month_label in ["Aug-26", "Sept-26"]:
        rows = []
        balance = 850000.0
        for i in range(70):
            d = rand_date()
            amount = round(random.uniform(-95000, 120000), 2)
            balance += amount
            rows.append(
                {
                    "Date": fmt_date(d, random.choice([0, 1, 2])),
                    "Voucher No": f"CB-{random.randint(1000, 9999)}",
                    "Description": random.choice(
                        [
                            "Yarn purchase payment",
                            "Buyer remittance received",
                            "Electricity bill payment",
                            "Staff salary disbursement",
                            "Diesel purchase for generator",
                            "Courier & freight charges",
                            "Bank charges - LC negotiation",
                            "Cash received from customer",
                            "",  # some rows genuinely blank in the description, on purpose
                        ]
                    ),
                    "Category": random.choice(FINANCE_CATEGORIES),
                    "Debit": abs(amount) if amount < 0 else "",
                    "Credit": amount if amount > 0 else "",
                    "Balance": round(balance, 2),
                    "Vendor/Customer": random.choice(VENDORS + CUSTOMERS + [""]),
                }
            )
        sheets[month_label] = pd.DataFrame(rows)
    path = FINANCE_DIR / "Cash_Book_Aug_Sept_2026.xlsx"
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        for name, df in sheets.items():
            df.to_excel(writer, sheet_name=name, index=False)
    print(f"[OK] {path.name}")


# ---------------------------------------------------------------------------
# Finance: PTIL Expenditure
# ---------------------------------------------------------------------------
def build_expenditure():
    rows = []
    for i in range(90):
        d = rand_date()
        currency = random.choice(CURRENCIES)
        amount = round(random.uniform(500, 45000) if currency == "BDT" else random.uniform(50, 3000), 2)
        rows.append(
            {
                "Date": fmt_date(d, random.choice([0, 1])),
                "Category": random.choice(FINANCE_CATEGORIES),
                "Vendor": random.choice(VENDORS),
                "Invoice No": f"INV-{random.randint(20000, 29999)}",
                "Amount": amount,
                "Currency": currency,
                "Payment Method": random.choice(["Bank Transfer", "Cash", "Cheque", "Mobile Banking"]),
                "Approved By": rand_name(),
            }
        )
    df = pd.DataFrame(rows)
    path = FINANCE_DIR / "PTIL_Expenditure_2026.xlsx"
    df.to_excel(path, sheet_name="Expenditure", index=False)
    print(f"[OK] {path.name}")


# ---------------------------------------------------------------------------
# Finance: Party Due Bill
# ---------------------------------------------------------------------------
def build_party_due_bill():
    rows = []
    for i in range(45):
        inv_date = rand_date(90)
        due_date = inv_date + timedelta(days=random.choice([30, 45, 60, 90]))
        aging_days = max((BASE_DATE + timedelta(days=55) - due_date).days, -10)
        bucket = "Not Due"
        if aging_days > 90:
            bucket = "90+ days"
        elif aging_days > 60:
            bucket = "61-90 days"
        elif aging_days > 30:
            bucket = "31-60 days"
        elif aging_days > 0:
            bucket = "0-30 days"
        rows.append(
            {
                "Customer": random.choice(CUSTOMERS),
                "Invoice Ref": f"PTIL-EXP-{random.randint(4000, 4999)}",
                "Invoice Date": fmt_date(inv_date, 0),
                "Due Date": fmt_date(due_date, 0),
                "Amount Due (USD)": round(random.uniform(3000, 85000), 2),
                "Aging Bucket": bucket,
                "Status": random.choice(["Outstanding", "Outstanding", "Partially Paid", "Cleared"]),
            }
        )
    df = pd.DataFrame(rows)
    path = FINANCE_DIR / "Party_Due_Bill_Sept2026.xlsx"
    df.to_excel(path, sheet_name="Party Due Bill", index=False)
    print(f"[OK] {path.name}")


# ---------------------------------------------------------------------------
# Finance: Profit & Loss Statement
# ---------------------------------------------------------------------------
def build_pnl():
    data = {
        "Line Item": [
            "Export Revenue", "Domestic Revenue", "Total Revenue",
            "Raw Material Cost", "Direct Labor", "Factory Overhead", "Total COGS",
            "Gross Profit",
            "Admin Expenses", "Selling & Distribution", "Finance Cost", "Total Operating Expense",
            "EBIT", "Tax Provision", "Net Profit",
        ],
        "Q1 2026 (BDT)": [
            42500000, 6800000, 49300000,
            21200000, 9800000, 4100000, 35100000,
            14200000,
            2100000, 1450000, 980000, 4530000,
            9670000, 1450000, 8220000,
        ],
        "Q2 2026 (BDT)": [
            45900000, 7200000, 53100000,
            22800000, 10100000, 4300000, 37200000,
            15900000,
            2250000, 1600000, 1020000, 4870000,
            11030000, 1650000, 9380000,
        ],
        "Q3 2026 (BDT)": [
            48100000, 6950000, 55050000,
            23950000, 10450000, 4500000, 38900000,
            16150000,
            2380000, 1720000, 1105000, 5205000,
            10945000, 1640000, 9305000,
        ],
    }
    df = pd.DataFrame(data)
    path = FINANCE_DIR / "Profit_and_Loss_Statement_2026.xlsx"
    df.to_excel(path, sheet_name="P&L Summary", index=False)
    print(f"[OK] {path.name}")


# ---------------------------------------------------------------------------
# Finance: LC Tracking Sheet
# ---------------------------------------------------------------------------
def build_lc_tracking():
    banks = ["HSBC Dhaka", "Standard Chartered Dhaka", "Eastern Bank Ltd.", "Dutch-Bangla Bank"]
    rows = []
    for i in range(28):
        issue = rand_date(80)
        expiry = issue + timedelta(days=random.choice([90, 120, 150]))
        shipment_deadline = expiry - timedelta(days=random.choice([10, 15, 20]))
        rows.append(
            {
                "LC Number": f"LC{random.randint(100000, 999999)}",
                "Issuing Bank": random.choice(banks),
                "Buyer": random.choice(CUSTOMERS),
                "Amount (USD)": round(random.uniform(25000, 480000), 2),
                "Issue Date": fmt_date(issue, 0),
                "Expiry Date": fmt_date(expiry, 0),
                "Shipment Deadline": fmt_date(shipment_deadline, 0),
                "Status": random.choice(["Active", "Active", "Documents Presented", "Payment Realized", "Amendment Requested"]),
            }
        )
    df = pd.DataFrame(rows)
    path = FINANCE_DIR / "LC_Tracking_Sheet.xlsx"
    df.to_excel(path, sheet_name="LC Tracking", index=False)
    print(f"[OK] {path.name}")


# ---------------------------------------------------------------------------
# Commercial: Order Release Log
# ---------------------------------------------------------------------------
def build_order_release_log():
    styles = ["PTIL-KN-401", "PTIL-KN-402", "PTIL-WV-118", "PTIL-KN-415", "PTIL-WV-122", "PTIL-KN-430"]
    rows = []
    for i in range(60):
        order_date = rand_date(70)
        delivery = order_date + timedelta(days=random.randint(35, 75))
        qty = random.randint(5000, 60000)
        unit_price = round(random.uniform(2.1, 8.75), 2)
        rows.append(
            {
                "Order No": f"PO-{random.randint(70000, 79999)}",
                "Buyer": random.choice(CUSTOMERS),
                "Style Ref": random.choice(styles),
                "Quantity (pcs)": qty,
                "Unit Price (USD)": unit_price,
                "Total Value (USD)": round(qty * unit_price, 2),
                "Order Date": fmt_date(order_date, 0),
                "Delivery Date": fmt_date(delivery, 0),
                "Status": random.choice(["Confirmed", "In Production", "Shipped", "Delayed", "Sample Stage"]),
            }
        )
    df = pd.DataFrame(rows)
    path = COMMERCIAL_DIR / "Order_Release_Log_2026.xlsx"
    df.to_excel(path, sheet_name="Order Releases", index=False)
    print(f"[OK] {path.name}")


def build_sample_approval_tracker():
    styles = ["PTIL-KN-401", "PTIL-KN-402", "PTIL-WV-118", "PTIL-KN-415", "PTIL-WV-122"]
    rows = []
    for i in range(25):
        sent = rand_date(70)
        approved = sent + timedelta(days=random.randint(3, 12))
        rows.append(
            {
                "Style Ref": random.choice(styles),
                "Buyer": random.choice(CUSTOMERS),
                "Sample Type": random.choice(["PP Sample", "Size Set", "Fit Sample", "Shipment Sample"]),
                "Sent Date": fmt_date(sent, 1),
                "Approved Date": fmt_date(approved, 1) if random.random() > 0.15 else "",
                "Status": random.choice(["Approved", "Approved", "Pending Buyer Feedback", "Rejected - Resubmit"]),
                "Remarks": random.choice(["", "Color shade slightly off", "Buyer requested trim change", "OK for bulk"]),
            }
        )
    df = pd.DataFrame(rows)
    path = COMMERCIAL_DIR / "Sample_Approval_Tracker.xlsx"
    df.to_excel(path, sheet_name="Sample Tracker", index=False)
    print(f"[OK] {path.name}")


# ---------------------------------------------------------------------------
# Admin: Asset Register + Visitor Log
# ---------------------------------------------------------------------------
def build_asset_register():
    asset_types = ["Laptop", "Desktop PC", "Industrial Sewing Machine", "Forklift", "Generator", "CCTV Camera", "Office AC Unit"]
    depts = ["Finance", "HR", "Commercial", "Admin", "Maintenance", "Production"]
    rows = []
    for i in range(50):
        purchase = rand_date(700)
        rows.append(
            {
                "Asset Tag": f"PTIL-A-{1000 + i}",
                "Description": random.choice(asset_types),
                "Assigned To": rand_name(),
                "Department": random.choice(depts),
                "Purchase Date": fmt_date(purchase, 0),
                "Value (BDT)": round(random.uniform(8000, 650000), 2),
                "Status": random.choice(["In Use", "In Use", "Under Repair", "Retired"]),
            }
        )
    df = pd.DataFrame(rows)
    path = ADMIN_DIR / "Asset_Register.xlsx"
    df.to_excel(path, sheet_name="Assets", index=False)
    print(f"[OK] {path.name}")


def build_visitor_log():
    purposes = ["Buyer Audit", "Bank Officer Visit", "Vendor Meeting", "Government Inspection", "Job Interview", "Courier Delivery"]
    rows = []
    for i in range(80):
        d = rand_date()
        time_in_hr = random.randint(9, 16)
        rows.append(
            {
                "Date": fmt_date(d, 1),
                "Visitor Name": rand_name(),
                "Company": random.choice(VENDORS + CUSTOMERS + ["Self-employed", "Bangladesh Bank"]),
                "Host Employee": rand_name(),
                "Purpose": random.choice(purposes),
                "Time In": f"{time_in_hr}:{random.choice(['00','15','30','45'])}",
                "Time Out": f"{time_in_hr + random.randint(1,3)}:{random.choice(['00','15','30','45'])}",
            }
        )
    df = pd.DataFrame(rows)
    path = ADMIN_DIR / "Visitor_Log_Sept2026.xlsx"
    df.to_excel(path, sheet_name="Visitor Log", index=False)
    print(f"[OK] {path.name}")


# ---------------------------------------------------------------------------
# Maintenance: Machine Downtime + Spare Parts Inventory
# ---------------------------------------------------------------------------
def build_machine_downtime():
    machine_types = ["Circular Knitting Machine", "Dyeing Machine", "Sewing Line", "Generator", "Boiler"]
    issues = ["Motor overheating", "Needle breakage", "Control board fault", "Belt slippage", "Pressure valve leak", "Power supply fluctuation"]
    rows = []
    for i in range(65):
        report_time = rand_date()
        downtime_min = random.randint(15, 480)
        rows.append(
            {
                "Machine ID": f"MC-{random.randint(100,199)}",
                "Type": random.choice(machine_types),
                "Issue": random.choice(issues),
                "Reported Time": fmt_date(report_time, 0) + f" {random.randint(6,22)}:00",
                "Downtime (min)": downtime_min,
                "Technician": rand_name(),
                "Root Cause Fixed": random.choice(["Yes", "Yes", "No - Escalated"]),
            }
        )
    df = pd.DataFrame(rows)
    path = MAINTENANCE_DIR / "Machine_Downtime_Log_2026.xlsx"
    df.to_excel(path, sheet_name="Downtime Log", index=False)
    print(f"[OK] {path.name}")


def build_spare_parts_inventory():
    parts = [
        ("Sewing Needle DBx1", "pcs"), ("Knitting Machine Belt", "pcs"), ("Motor Bearing 6205", "pcs"),
        ("Control Board Fuse 10A", "pcs"), ("Generator Fuel Filter", "pcs"), ("Boiler Pressure Gauge", "pcs"),
        ("Dyeing Machine Nozzle", "pcs"), ("Hydraulic Oil 20L", "drum"),
    ]
    rows = []
    for name, unit in parts:
        stock = random.randint(2, 120)
        threshold = random.randint(10, 30)
        rows.append(
            {
                "Part No": f"SP-{random.randint(1000,1999)}",
                "Description": name,
                "Unit": unit,
                "Stock Qty": stock,
                "Reorder Threshold": threshold,
                "Unit Cost (BDT)": round(random.uniform(50, 12000), 2),
                "Last Ordered": fmt_date(rand_date(60), 0),
                "Status": "LOW STOCK - REORDER" if stock < threshold else "OK",
            }
        )
    df = pd.DataFrame(rows)
    path = MAINTENANCE_DIR / "Spare_Parts_Inventory.xlsx"
    df.to_excel(path, sheet_name="Spare Parts", index=False)
    print(f"[OK] {path.name}")


# ---------------------------------------------------------------------------
# HR: Employee Master List + Attendance Summary
# ---------------------------------------------------------------------------
def build_employee_master_list():
    depts = ["Finance", "HR", "Commercial", "Admin", "Maintenance", "Production", "Accounting"]
    designations = ["Executive", "Senior Executive", "Assistant Manager", "Manager", "Line Supervisor", "Machine Operator"]
    rows = []
    for i in range(120):
        joined = BASE_DATE - timedelta(days=random.randint(30, 2500))
        rows.append(
            {
                "Employee ID": f"PTIL-{2000+i}",
                "Name": rand_name(),
                "Department": random.choice(depts),
                "Designation": random.choice(designations),
                "Date Joined": fmt_date(joined, 0),
                "Salary (BDT)": random.choice([12000, 15000, 18500, 22000, 28000, 35000, 55000, 72000]),
                "Status": random.choice(["Active", "Active", "Active", "On Leave", "Resigned"]),
            }
        )
    df = pd.DataFrame(rows)
    path = HR_DIR / "Employee_Master_List.xlsx"
    df.to_excel(path, sheet_name="Employees", index=False)
    print(f"[OK] {path.name}")


def build_attendance_summary():
    rows = []
    for i in range(120):
        present = random.randint(18, 26)
        rows.append(
            {
                "Employee ID": f"PTIL-{2000+i}",
                "Name": rand_name(),
                "Days Present": present,
                "Days Absent": max(0, 26 - present - random.randint(0, 2)),
                "Late Arrivals": random.randint(0, 5),
                "Leave Taken": random.randint(0, 3),
                "Month": "September 2026",
            }
        )
    df = pd.DataFrame(rows)
    path = HR_DIR / "Attendance_Summary_Sept2026.xlsx"
    df.to_excel(path, sheet_name="Attendance", index=False)
    print(f"[OK] {path.name}")


# ---------------------------------------------------------------------------
# Accounting: Petty Cash Ledger + Expense Claims Log
# ---------------------------------------------------------------------------
def build_petty_cash_ledger():
    depts = ["Finance", "HR", "Commercial", "Admin", "Maintenance"]
    purposes = ["Office stationery", "Local transport", "Courier charges", "Minor repair materials", "Refreshments for buyer visit"]
    rows = []
    balance = 40000.0
    for i in range(55):
        d = rand_date()
        amount = round(random.uniform(150, 4800), 2)
        balance -= amount
        rows.append(
            {
                "Date": fmt_date(d, 2),
                "Department": random.choice(depts),
                "Purpose": random.choice(purposes),
                "Amount (BDT)": amount,
                "Approved By": rand_name(),
                "Receipt No": f"PC-{random.randint(500,999)}",
                "Running Balance": round(balance, 2),
            }
        )
    df = pd.DataFrame(rows)
    path = ACCOUNTING_DIR / "Petty_Cash_Ledger_Sept2026.xlsx"
    df.to_excel(path, sheet_name="Petty Cash", index=False)
    print(f"[OK] {path.name}")


def build_expense_claims_log():
    depts = ["Finance", "HR", "Commercial", "Admin", "Maintenance"]
    rows = []
    for i in range(40):
        submitted = rand_date()
        rows.append(
            {
                "Claim ID": f"EC-{random.randint(3000,3999)}",
                "Employee": rand_name(),
                "Department": random.choice(depts),
                "Amount (BDT)": round(random.uniform(500, 6500), 2),
                "Category": random.choice(["Travel", "Client Entertainment", "Office Supplies", "Repair"]),
                "Status": random.choice(["Reimbursed", "Reimbursed", "Pending Approval", "Rejected"]),
                "Date Submitted": fmt_date(submitted, 1),
            }
        )
    df = pd.DataFrame(rows)
    path = ACCOUNTING_DIR / "Expense_Claims_Log.xlsx"
    df.to_excel(path, sheet_name="Expense Claims", index=False)
    print(f"[OK] {path.name}")


# ---------------------------------------------------------------------------
# Word documents
# ---------------------------------------------------------------------------
def build_po_confirmation_letter():
    doc = Document()
    doc.add_heading("Purchase Order Confirmation", level=1)
    p = doc.add_paragraph()
    p.add_run("Precision Textile Industry Ltd.\nGazipur, Dhaka, Bangladesh\n").bold = True
    doc.add_paragraph(f"Date: {fmt_date(rand_date(20), 0)}")
    doc.add_paragraph(f"To: {random.choice(CUSTOMERS)}")
    doc.add_paragraph(
        "\nWe are pleased to confirm receipt and acceptance of your Purchase Order "
        f"referenced below, and confirm production scheduling as per the terms discussed."
    )
    doc.add_heading("Order Details", level=2)
    table = doc.add_table(rows=1, cols=2)
    table.style = "Light Grid Accent 1"
    hdr = table.rows[0].cells
    hdr[0].text, hdr[1].text = "Field", "Value"
    details = [
        ("PO Number", f"PO-{random.randint(70000,79999)}"),
        ("Style Reference", "PTIL-KN-415"),
        ("Quantity", f"{random.randint(10000,40000)} pcs"),
        ("Unit Price", f"USD {round(random.uniform(3.0,7.5),2)}"),
        ("Estimated Delivery", fmt_date(rand_date(70) + timedelta(days=45), 0)),
        ("Payment Terms", "Irrevocable Letter of Credit at sight"),
    ]
    for k, v in details:
        row = table.add_row().cells
        row[0].text, row[1].text = k, v
    doc.add_paragraph(
        "\nPlease note that any change to quantity, style specification, or delivery "
        "date must be communicated in writing at least 10 working days before the "
        "scheduled shipment date to avoid production delays."
    )
    doc.add_paragraph("\nRegards,")
    doc.add_paragraph(f"{rand_name()}\nAssistant Commercial Manager\nPrecision Textile Industry Ltd.")
    path = COMMERCIAL_DIR / "Buyer_PO_Confirmation_Letter.docx"
    doc.save(path)
    print(f"[OK] {path.name}")


def build_financial_summary_report():
    doc = Document()
    doc.add_heading("Q3 2026 Financial Summary Report", level=1)
    doc.add_paragraph("Precision Textile Industry Ltd. — Finance Department")
    doc.add_paragraph(f"Prepared by: {rand_name()}, Commercial Manager")
    doc.add_paragraph(f"Date: {fmt_date(rand_date(10), 0)}")

    doc.add_heading("Overview", level=2)
    doc.add_paragraph(
        "Total revenue for Q3 2026 reached BDT 55,050,000, representing a 3.7% increase "
        "over Q2 2026. Export orders continued to drive the majority of revenue, with "
        "domestic sales remaining a smaller but stable contribution."
    )

    doc.add_heading("Key Observations", level=2)
    for bullet in [
        "Raw material costs rose slightly due to yarn price fluctuations in the regional market.",
        "Finance cost increased due to higher LC negotiation volume during the quarter.",
        "Net profit margin held steady at approximately 16.9%, consistent with prior quarter.",
        "Outstanding party dues in the 61-90 day bucket increased and should be monitored closely.",
    ]:
        doc.add_paragraph(bullet, style="List Bullet")

    doc.add_heading("Recommendation", level=2)
    doc.add_paragraph(
        "Continue current cost control measures on raw material procurement, and "
        "prioritize collection follow-up on aged party dues exceeding 60 days to "
        "improve cash flow position heading into Q4 2026."
    )
    path = FINANCE_DIR / "Q3_2026_Financial_Summary_Report.docx"
    doc.save(path)
    print(f"[OK] {path.name}")


# ---------------------------------------------------------------------------
# PDFs
# ---------------------------------------------------------------------------
def build_invoice_pdf():
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "COMMERCIAL INVOICE", ln=True)
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 8, "Precision Textile Industry Ltd. - Gazipur, Dhaka, Bangladesh", ln=True)
    pdf.ln(4)

    invoice_no = f"PTIL-INV-{random.randint(5000,5999)}"
    buyer = random.choice(CUSTOMERS)
    date = fmt_date(rand_date(30), 0)
    qty = random.randint(8000, 30000)
    unit_price = round(random.uniform(3.2, 7.8), 2)
    total = round(qty * unit_price, 2)

    for label, value in [
        ("Invoice No", invoice_no),
        ("Date", date),
        ("Buyer", buyer),
        ("Style Reference", "PTIL-KN-402"),
        ("Quantity", f"{qty} pcs"),
        ("Unit Price", f"USD {unit_price}"),
        ("Total Value", f"USD {total}"),
        ("Payment Terms", "Irrevocable LC at sight"),
        ("Port of Loading", "Chattogram, Bangladesh"),
        ("Port of Discharge", "Hamburg, Germany"),
    ]:
        pdf.cell(60, 8, label + ":", border=0)
        pdf.cell(0, 8, str(value), ln=True)

    pdf.ln(6)
    pdf.multi_cell(
        0, 7,
        "This invoice is issued in accordance with the terms of the Letter of Credit "
        "opened in favor of Precision Textile Industry Ltd. and is presented together "
        "with the packing list, bill of lading, and certificate of origin for bank negotiation."
    )
    path = COMMERCIAL_DIR / "Invoice_Sample.pdf"
    pdf.output(str(path))
    print(f"[OK] {path.name}")


def build_lc_copy_pdf():
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "IRREVOCABLE DOCUMENTARY LETTER OF CREDIT", ln=True)
    pdf.set_font("Helvetica", "", 11)
    pdf.ln(2)

    lc_number = f"LC{random.randint(100000,999999)}"
    issue_date = fmt_date(rand_date(60), 0)
    expiry_date = fmt_date(rand_date(60) + timedelta(days=120), 0)
    amount = round(random.uniform(80000, 350000), 2)
    buyer = random.choice(CUSTOMERS)

    for label, value in [
        ("LC Number", lc_number),
        ("Issuing Bank", "Standard Chartered Bank, Dhaka"),
        ("Applicant (Buyer)", buyer),
        ("Beneficiary", "Precision Textile Industry Ltd., Gazipur, Bangladesh"),
        ("Amount", f"USD {amount}"),
        ("Date of Issue", issue_date),
        ("Date and Place of Expiry", f"{expiry_date}, in Bangladesh"),
        ("Latest Shipment Date", fmt_date(rand_date(60) + timedelta(days=100), 0)),
        ("Partial Shipment", "Not Allowed"),
        ("Documents Required", "Commercial Invoice, Packing List, Bill of Lading, Certificate of Origin"),
    ]:
        pdf.cell(70, 8, label + ":", border=0)
        pdf.cell(0, 8, str(value), ln=True)

    pdf.ln(6)
    pdf.multi_cell(
        0, 7,
        "This Letter of Credit is subject to the Uniform Customs and Practice for "
        "Documentary Credits (UCP 600), and payment shall be effected upon presentation "
        "of complying documents within the stipulated presentation period."
    )
    path = FINANCE_DIR / "LC_Copy_Sample.pdf"
    pdf.output(str(path))
    print(f"[OK] {path.name}")


def main():
    print("Generating messy dummy PTIL dataset...\n")
    build_cash_book()
    build_expenditure()
    build_party_due_bill()
    build_pnl()
    build_lc_tracking()
    build_financial_summary_report()
    build_invoice_pdf()
    build_lc_copy_pdf()

    build_order_release_log()
    build_sample_approval_tracker()
    build_po_confirmation_letter()

    build_asset_register()
    build_visitor_log()

    build_machine_downtime()
    build_spare_parts_inventory()

    build_employee_master_list()
    build_attendance_summary()

    build_petty_cash_ledger()
    build_expense_claims_log()

    print("\nDone. Files written under backend/seed_docs/<owner folder>/")


if __name__ == "__main__":
    main()
