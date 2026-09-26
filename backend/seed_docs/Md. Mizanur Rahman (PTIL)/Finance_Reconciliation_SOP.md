# PTIL — Daily Finance Reconciliation SOP

**Department:** Finance & Accounting
**Owner:** Commercial Manager (Md. Mizanur Rahman)

## Purpose

Standardizes how daily cash book entries, party due bills, and expenditure
records are reconciled between the Google Drive finance workbooks and the
company's financial reporting system.

## Daily Workflow

1. **Cash Book Entry**: The accounting assistant records all cash
   transactions (payments received, payments made, petty cash) in the daily
   Cash Book workbook stored in the Finance Google Drive folder.
2. **Party Due Bill Update**: Any outstanding customer or supplier balances
   are updated in the Party Due Bill sheet, categorized by customer name,
   invoice reference, and due date.
3. **Expenditure Logging**: Operational expenditures (utilities, raw
   material purchases, LC-related charges) are logged in the PTIL
   Expenditure workbook with a category tag (Utilities, Raw Materials,
   Logistics, LC Charges, Maintenance).
4. **End-of-Day Reconciliation**: By 6:00 PM, the finance dashboard should
   reflect the day's transactions, with any variance greater than ৳1,000
   (or $100 USD) flagged for manual review.

## Reconciliation Tolerance

The ingested sum in the system must match the source workbook total within
±$100 USD or ±1,000 BDT. Discrepancies beyond this threshold are logged in
the error tracking table and routed to the Commercial Manager for review.

## Monthly Close

On the 1st of each month, the previous month's Cash Book and Expenditure
workbooks are archived, and a summary report is generated covering:
- Total revenue collected
- Total expenditure by category
- Outstanding party dues (aging analysis: 0–30, 31–60, 61–90, 90+ days)
- Cash flow position for the month

## Currency Handling

PTIL transacts primarily in BDT (Bangladeshi Taka), with USD used for
export-related Letter of Credit (LC) transactions. All USD figures are
converted to BDT using the Bangladesh Bank reference rate at time of
recording.
