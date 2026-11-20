"""XLSX builders for payment batches, reconciliation statements, evidence packs and statements."""

from __future__ import annotations

from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

HEADER_FILL = PatternFill("solid", fgColor="1F3A5F")
HEADER_FONT = Font(bold=True, color="FFFFFF")


def _safe(value):
    """Neutralise spreadsheet formula injection from user-supplied text."""
    if isinstance(value, str) and value[:1] in ("=", "+", "-", "@"):
        return "'" + value
    return value


def _table(ws, headers: list[str], rows: list[list], start_row: int = 1) -> None:
    for col, title in enumerate(headers, start=1):
        cell = ws.cell(row=start_row, column=col, value=title)
        cell.fill, cell.font = HEADER_FILL, HEADER_FONT
    for r, row in enumerate(rows, start=start_row + 1):
        for c, value in enumerate(row, start=1):
            ws.cell(row=r, column=c, value=_safe(value))
    _autosize(ws)


def _autosize(ws) -> None:
    for col in ws.columns:
        width = max((len(str(c.value)) for c in col if c.value is not None), default=8)
        ws.column_dimensions[get_column_letter(col[0].column)].width = min(max(width + 2, 10), 60)


def _kv(ws, pairs: list[tuple], start_row: int = 1) -> int:
    for i, (k, v) in enumerate(pairs, start=start_row):
        ws.cell(row=i, column=1, value=k).font = Font(bold=True)
        ws.cell(row=i, column=2, value=_safe(v))
    _autosize(ws)
    return start_row + len(pairs)


def _to_bytes(wb: Workbook) -> bytes:
    out = BytesIO()
    wb.save(out)
    return out.getvalue()


def payment_batch_xlsx(batch: dict, items: list[dict]) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Batch"
    _kv(
        ws,
        [
            ("Batch", batch["name"]),
            ("Payment date", batch["paymentDate"]),
            ("Status", batch["status"]),
            ("Invoices", batch["itemCount"]),
            ("Total amount", batch["totalAmount"]),
        ],
    )
    sheet = wb.create_sheet("Invoices")
    _table(
        sheet,
        ["Vendor", "Invoice no.", "Invoice date", "Due date", "GL account", "Amount", "Document"],
        [
            [i["vendor"], i["invoiceNumber"], i["invoiceDate"], i["dueDate"], i["accountCode"], i["amount"], i["documentName"]]
            for i in items
        ],
    )
    return _to_bytes(wb)


def reconciliation_statement_xlsx(doc_name: str, summary: dict, totals: dict, exceptions: list[dict], matched: list[dict]) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Statement"
    _kv(
        ws,
        [
            ("Workbook", doc_name),
            ("Cashbook transactions", summary.get("cashbookTransactionCount")),
            ("Bank transactions", summary.get("bankTransactionCount")),
            ("Matched pairs", totals["matchedCount"]),
            ("Matched amount", totals["matchedTotal"]),
            ("Open cashbook items (not on bank)", totals["openCashbookCount"]),
            ("Open cashbook amount", totals["openCashbookTotal"]),
            ("Open bank items (not in cashbook)", totals["openBankCount"]),
            ("Open bank amount", totals["openBankTotal"]),
            ("Resolved exceptions", totals["resolvedCount"]),
            ("Written-off exceptions", totals["writtenOffCount"]),
            ("Written-off amount", totals["writtenOffTotal"]),
            ("Matching policy", summary.get("matchingPolicy")),
        ],
    )
    _table(
        wb.create_sheet("Exceptions"),
        ["Side", "Row", "Date", "Description", "Reference", "Direction", "Amount", "Reason", "Status", "Note"],
        [
            [e["side"], e["row"], e["date"], e["description"], e["reference"], e["direction"], e["amount"], e["reasonText"], e["status"], e["note"]]
            for e in exceptions
        ],
    )
    _table(
        wb.create_sheet("Matched"),
        ["Cashbook row", "Bank row", "Date", "Description", "Amount", "Method"],
        [
            [m["cashbook"].get("row"), m["bankStatement"].get("row"), m["cashbook"].get("date"), m["cashbook"].get("description"), m["cashbook"].get("amount"), m.get("matchMethod")]
            for m in matched
        ],
    )
    return _to_bytes(wb)


def evidence_pack_xlsx(risk: dict, document: dict, related: list[dict], audit: list[dict], reviews: list[dict]) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Summary"
    _kv(
        ws,
        [
            ("Document", document["name"]),
            ("Vendor", document["vendor"]),
            ("Invoice no.", document["invoiceNumber"]),
            ("Amount", document["amount"]),
            ("Uploaded by", document["owner"]),
            ("Risk score", risk["score"]),
            ("Risk band", risk["band"]),
            ("Disclaimer", "Rule-based signals for human review. Not proof of fraud."),
        ],
    )
    _table(
        wb.create_sheet("Risk rules"),
        ["Rule", "Weight", "What it means", "Detail"],
        [[r["code"], r["weight"], r["description"], r["detail"]] for r in risk["rules"]],
    )
    _table(
        wb.create_sheet("Related documents"),
        ["ID", "Name", "Vendor", "Invoice no.", "Amount", "Date", "Why related"],
        [[d["id"], d["name"], d["vendor"], d["invoiceNumber"], d["amount"], d["date"], d["why"]] for d in related],
    )
    _table(
        wb.create_sheet("Audit history"),
        ["When", "Action", "By", "Reason"],
        [[a["when"], a["action"], a["actor"], a["reason"]] for a in audit],
    )
    _table(
        wb.create_sheet("Review notes"),
        ["Signal", "Status", "Note", "Reviewed by", "Reviewed at"],
        [[r["signal"], r["status"], r["note"], r["reviewer"], r["reviewedAt"]] for r in reviews],
    )
    return _to_bytes(wb)


def statements_xlsx(data: dict, comparison: dict | None, commentary: list[str]) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Summary"
    pl, bs, cf = data["profitAndLoss"], data["balanceSheet"], data["cashFlow"]
    _kv(
        ws,
        [
            ("Period", f"{data['period']['start']} to {data['period']['end']}"),
            ("Revenue", pl["revenue"]["total"]),
            ("Gross profit", pl["grossProfit"]),
            ("Net profit", pl["netProfit"]),
            ("Total assets", bs["assets"]["total"]),
            ("Net change in cash", cf["netChangeInCash"]),
            ("Warnings", " | ".join(data["warnings"]) or "None"),
        ],
    )

    sheet = wb.create_sheet("P&L")
    rows: list[list] = []
    for title, key in (("Revenue", "revenue"), ("Cost of goods sold", "costOfGoodsSold"), ("Operating expenses", "operatingExpenses")):
        rows.append([title, None, None])
        rows += [[r["code"], r["name"], r["amount"]] for r in pl[key]["rows"]]
        rows.append(["", f"Total {title.lower()}", pl[key]["total"]])
    rows += [["", "Gross profit", pl["grossProfit"]], ["", "Net profit", pl["netProfit"]]]
    _table(sheet, ["Code", "Account", "Amount"], rows)

    sheet = wb.create_sheet("Balance Sheet")
    rows = []
    for title, key in (("Assets", "assets"), ("Liabilities", "liabilities"), ("Equity", "equity")):
        rows.append([title, None, None])
        rows += [[r["code"], r["name"], r["amount"]] for r in bs[key]["rows"]]
        if key == "equity":
            rows.append(["", "Current earnings", bs["equity"]["currentEarnings"]])
        rows.append(["", f"Total {title.lower()}", bs[key]["total"]])
    rows.append(["", "Balance check (should be 0)", bs["balanceCheck"]])
    _table(sheet, ["Code", "Account", "Amount"], rows)

    sheet = wb.create_sheet("Cash Flow")
    _table(
        sheet,
        ["Item", "Amount"],
        [
            ["Net profit", cf["operating"]["netProfit"]],
            ["Change in other assets", cf["operating"]["changeInOtherAssets"]],
            ["Change in other liabilities", cf["operating"]["changeInOtherLiabilities"]],
            ["Operating cash flow", cf["operating"]["total"]],
            ["Investing cash flow", cf["investing"]["total"]],
            ["Financing cash flow", cf["financing"]["total"]],
            ["Net change in cash (calculated)", cf["netChangeInCash"]],
            ["Opening cash", cf["openingCash"]],
            ["Closing cash", cf["closingCash"]],
            ["Actual change in cash", cf["actualChangeInCash"]],
            ["Unexplained difference", cf["unexplainedDifference"]],
            ["Method", cf["method"]],
        ],
    )

    # Trial Balance and General Ledger are included in the same workbook.
    tb = data.get("trialBalance") or {"rows": [], "totalDebit": 0, "totalCredit": 0}
    sheet = wb.create_sheet("Trial Balance")
    _table(sheet, ["Code", "Account", "Debit", "Credit"],
           [[r["code"], r["name"], r["debit"], r["credit"]] for r in tb.get("rows", [])]
           + [["", "TOTAL", tb.get("totalDebit", 0), tb.get("totalCredit", 0)]])

    sheet = wb.create_sheet("General Ledger")
    gl_rows = data.get("generalLedger") or []
    _table(sheet, ["Date", "Voucher", "Account Code", "Account", "Narration", "Debit", "Credit", "Running Balance"],
           [[r.get("date"), r.get("voucherNo"), r.get("accountCode"), r.get("accountName"), r.get("narration"), r.get("debit"), r.get("credit"), r.get("runningBalance")] for r in gl_rows])

    if comparison:
        sheet = wb.create_sheet("Variance")
        _table(
            sheet,
            ["Metric", "Previous", "Current", "Variance", "Variance %"],
            [[v["metric"], v["previous"], v["current"], v["variance"], v["variancePct"]] for v in comparison["variances"]],
        )
        com = wb.create_sheet("Commentary")
        for i, line in enumerate(commentary, start=1):
            com.cell(row=i, column=1, value=_safe(line))
        com.column_dimensions["A"].width = 120
    return _to_bytes(wb)


def operational_report_xlsx(report: dict) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Summary"
    _kv(ws, [("Report", report.get("reportType")), ("Start", report.get("start") or "All"),
             ("End", report.get("end") or "All"), ("Invoice count", report.get("count", 0)),
             ("Total amount", report.get("totalAmount", 0)),
             ("Outstanding amount", report.get("outstandingAmount", 0)),
             ("Basis", report.get("basis", ""))])
    rows = report.get("rows", [])
    sheet = wb.create_sheet("Invoices")
    _table(sheet, ["Document ID", "Document", "Party", "Invoice Number", "Invoice Date", "Due Date",
                   "Amount", "Status", "Approval Status", "Validation Status"],
           [[r.get("documentId"), r.get("documentName"), r.get("party"), r.get("invoiceNumber"),
             r.get("invoiceDate"), r.get("dueDate"), r.get("amount"), r.get("status"),
             r.get("approvalStatus"), r.get("validationStatus")] for r in rows])
    return _to_bytes(wb)
