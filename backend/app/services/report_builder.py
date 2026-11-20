"""Builds the Financial Report data set and a formatted XLSX file.

Pure functions (no DB access) so they are easy to test. Figures come only from
extracted document fields; nothing is estimated.
"""

from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from io import BytesIO
from zoneinfo import ZoneInfo

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

INR_FORMAT = '"₹"#,##,##0.00'
HEADER_FILL = PatternFill("solid", fgColor="1F3A5F")
HEADER_FONT = Font(bold=True, color="FFFFFF")
THIN = Side(style="thin", color="D0D5DD")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)

LIMITATIONS = (
    "Totals include only extracted document total_amount values and are not a "
    "substitute for a complete general ledger."
)


def _zone(name: str):
    try:
        return ZoneInfo(name)
    except Exception:
        return timezone.utc


def _amount(value) -> Decimal:
    try:
        return Decimal(str(value)) if value is not None else Decimal("0")
    except Exception:
        return Decimal("0")


def _f(value: Decimal) -> float:
    return float(round(value, 2))


def build_report_data(
    docs, *, name: str, period: str | None, generated_by: str, timezone_name: str = "UTC"
) -> dict:
    by_category = defaultdict(lambda: {"count": 0, "amount": Decimal("0")})
    by_status = defaultdict(lambda: {"count": 0, "amount": Decimal("0")})
    by_vendor = defaultdict(lambda: {"count": 0, "amount": Decimal("0")})
    total = Decimal("0")
    with_amounts = 0
    rows = []

    for d in docs:
        amount = _amount(d.total_amount)
        category = (d.category or "Uncategorized").strip() or "Uncategorized"
        status = str(d.status or "UNKNOWN").upper()
        by_category[category]["count"] += 1
        by_category[category]["amount"] += amount
        by_status[status]["count"] += 1
        by_status[status]["amount"] += amount
        if d.vendor_name:
            by_vendor[d.vendor_name.strip()]["count"] += 1
            by_vendor[d.vendor_name.strip()]["amount"] += amount
        if d.total_amount is not None:
            with_amounts += 1
            total += amount
        rows.append({
            "id": d.id,
            "name": d.name,
            "category": category,
            "vendor": d.vendor_name or "",
            "invoiceNumber": d.invoice_number or "",
            "invoiceDate": d.invoice_date.isoformat() if d.invoice_date else "",
            "dueDate": d.due_date.isoformat() if d.due_date else "",
            "totalAmount": _f(amount) if d.total_amount is not None else None,
            "status": status,
            "reviewStatus": str(d.review_status or ""),
        })

    def table(source, key):
        return sorted(
            ({key: k, "count": v["count"], "amount": _f(v["amount"])} for k, v in source.items()),
            key=lambda item: item["amount"],
            reverse=True,
        )

    approved = [r for r in rows if r["reviewStatus"] == "APPROVED" and r["totalAmount"] is not None]
    pending = [r for r in rows if r["reviewStatus"] == "READY_FOR_REVIEW" and r["totalAmount"] is not None]

    return {
        "title": name,
        "period": period or "Not specified",
        "generatedBy": generated_by,
        "generatedAt": datetime.now(_zone(timezone_name)).strftime("%d %b %Y %H:%M %Z"),
        "summary": {
            "documentCount": len(rows),
            "documentsWithExtractedAmounts": with_amounts,
            "knownExtractedAmountTotal": _f(total),
            "approvedAmount": _f(sum((_amount(r["totalAmount"]) for r in approved), Decimal("0"))),
            "pendingApprovalAmount": _f(sum((_amount(r["totalAmount"]) for r in pending), Decimal("0"))),
            "categorizedDocumentCount": sum(1 for r in rows if r["category"].lower() != "uncategorized"),
        },
        "byCategory": table(by_category, "category"),
        "byStatus": table(by_status, "status"),
        "topVendors": table(by_vendor, "vendor")[:10],
        "documents": rows,
        "limitations": LIMITATIONS,
    }


def _style_header(sheet, row: int, ncols: int) -> None:
    for col in range(1, ncols + 1):
        cell = sheet.cell(row=row, column=col)
        cell.fill, cell.font, cell.border = HEADER_FILL, HEADER_FONT, BORDER
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)


def _write_table(sheet, start_row: int, headers, rows, money_cols=()) -> int:
    for i, header in enumerate(headers, start=1):
        sheet.cell(row=start_row, column=i, value=header)
    _style_header(sheet, start_row, len(headers))
    row_no = start_row
    for row_no, values in enumerate(rows, start=start_row + 1):
        for col, value in enumerate(values, start=1):
            cell = sheet.cell(row=row_no, column=col, value=value)
            cell.border = BORDER
            if col in money_cols:
                cell.number_format = INR_FORMAT
                cell.alignment = Alignment(horizontal="right")
    return row_no + 2


def _autowidth(sheet, minimum=12, maximum=48) -> None:
    widths = defaultdict(int)
    for row in sheet.iter_rows():
        for cell in row:
            if cell.value is not None:
                widths[cell.column] = max(widths[cell.column], len(str(cell.value)))
    for col, width in widths.items():
        sheet.column_dimensions[get_column_letter(col)].width = max(minimum, min(maximum, width + 2))


def build_report_xlsx(data: dict) -> bytes:
    """Render the report workbook entirely in memory and return its bytes."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Summary"
    ws["A1"] = data["title"]
    ws["A1"].font = Font(bold=True, size=16, color="1F3A5F")
    ws["A2"] = f"Period: {data['period']}"
    ws["A3"] = f"Generated: {data['generatedAt']} by {data['generatedBy']}"
    for ref in ("A2", "A3"):
        ws[ref].font = Font(color="475467")

    s = data["summary"]
    money = {"knownExtractedAmountTotal", "approvedAmount", "pendingApprovalAmount"}
    labels = [
        ("Documents analysed", s["documentCount"], "documentCount"),
        ("Documents with extracted amounts", s["documentsWithExtractedAmounts"], "documentsWithExtractedAmounts"),
        ("Categorised documents", s["categorizedDocumentCount"], "categorizedDocumentCount"),
        ("Total extracted amount", s["knownExtractedAmountTotal"], "knownExtractedAmountTotal"),
        ("Approved amount", s["approvedAmount"], "approvedAmount"),
        ("Awaiting approval amount", s["pendingApprovalAmount"], "pendingApprovalAmount"),
    ]
    nxt = _write_table(ws, 5, ["Metric", "Value"], [(a, b) for a, b, _ in labels])
    for i, (_, _, key) in enumerate(labels, start=6):
        if key in money:
            ws.cell(row=i, column=2).number_format = INR_FORMAT
    nxt = _write_table(ws, nxt, ["Category", "Documents", "Amount"],
                       [(r["category"], r["count"], r["amount"]) for r in data["byCategory"]], money_cols=(3,))
    nxt = _write_table(ws, nxt, ["Status", "Documents", "Amount"],
                       [(r["status"], r["count"], r["amount"]) for r in data["byStatus"]], money_cols=(3,))
    nxt = _write_table(ws, nxt, ["Top vendors", "Documents", "Amount"],
                       [(r["vendor"], r["count"], r["amount"]) for r in data["topVendors"]], money_cols=(3,))
    ws.cell(row=nxt, column=1, value=data["limitations"]).font = Font(italic=True, color="667085")
    _autowidth(ws)
    ws.column_dimensions["A"].width = 38

    dsheet = wb.create_sheet("Documents")
    headers = ["ID", "Document", "Category", "Vendor", "Invoice no.", "Invoice date", "Due date",
               "Total (INR)", "Status", "Review status"]
    rows = [(r["id"], r["name"], r["category"], r["vendor"], r["invoiceNumber"], r["invoiceDate"],
             r["dueDate"], r["totalAmount"], r["status"], r["reviewStatus"]) for r in data["documents"]]
    _write_table(dsheet, 1, headers, rows, money_cols=(8,))
    dsheet.freeze_panes = "A2"
    if rows:
        dsheet.auto_filter.ref = f"A1:{get_column_letter(len(headers))}{len(rows) + 1}"
    _autowidth(dsheet)

    for sheet in wb.worksheets:
        sheet.sheet_view.showGridLines = False
    buffer = BytesIO()
    wb.save(buffer)
    wb.close()
    return buffer.getvalue()
