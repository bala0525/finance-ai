"""P&L, Balance Sheet and Cash Flow from ledger accounts + journal lines.

Pure functions (no DB). Cash flow uses the indirect method with name-based
classification of accounts; any amount the classification cannot explain is shown as
an explicit "unexplained difference" instead of being forced to balance.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from io import BytesIO

from openpyxl import Workbook, load_workbook

from app.services.coding import DEFAULT_CHART

TYPE_ALIASES = {
    "ASSET": "ASSET", "ASSETS": "ASSET",
    "LIABILITY": "LIABILITY", "LIABILITIES": "LIABILITY",
    "EQUITY": "EQUITY", "CAPITAL": "EQUITY",
    "INCOME": "INCOME", "REVENUE": "INCOME", "SALES": "INCOME",
    "EXPENSE": "EXPENSE", "EXPENSES": "EXPENSE",
}
CASH_RE = re.compile(r"\b(cash|bank)\b", re.I)
FIXED_RE = re.compile(r"fixed|equipment|machinery|furniture|vehicle|building|property|plant|computer|land", re.I)
LOAN_RE = re.compile(r"loan|borrowing|debenture", re.I)
COGS_RE = re.compile(r"cost of goods|cogs|cost of sales|purchases", re.I)
MAX_IMPORT_ROWS = 20000


def normalise_type(value) -> str | None:
    return TYPE_ALIASES.get(str(value or "").strip().upper())


def _money(value) -> float:
    return round(float(value or 0), 2)


def _signed(account_type: str, debit: float, credit: float) -> float:
    return debit - credit if account_type in {"ASSET", "EXPENSE"} else credit - debit


def _balances(accounts: dict, lines: list[dict], start: date | None, end: date | None) -> dict[str, float]:
    totals: dict[str, float] = {}
    for line in lines:
        account = accounts.get(line["account_code"])
        if account is None:
            continue
        when = line["date"]
        if start and when < start:
            continue
        if end and when > end:
            continue
        totals[account["code"]] = totals.get(account["code"], 0.0) + _signed(
            account["type"], float(line["debit"]), float(line["credit"])
        )
    return totals


def build_statements(accounts: list[dict], lines: list[dict], start: date, end: date) -> dict:
    if start > end:
        raise ValueError("Period start must not be after period end.")

    chart: dict[str, dict] = {}
    warnings: list[str] = []
    for a in accounts:
        kind = normalise_type(a.get("type"))
        if kind is None:
            warnings.append(f"Account {a.get('code')} has an unknown type '{a.get('type')}' and was ignored.")
            continue
        chart[str(a["code"])] = {"code": str(a["code"]), "name": a["name"], "type": kind}

    unknown_lines = sum(1 for l in lines if str(l["account_code"]) not in chart)
    if unknown_lines:
        warnings.append(f"{unknown_lines} journal line(s) used account codes missing from the chart and were ignored.")
    lines = [{**l, "account_code": str(l["account_code"])} for l in lines]

    period = _balances(chart, lines, start, end)

    # ---- Profit & Loss (period movement) ----
    def pl_rows(kind: str, want_cogs: bool | None = None) -> list[dict]:
        rows = []
        for code, amount in period.items():
            acct = chart[code]
            if acct["type"] != kind or round(amount, 2) == 0:
                continue
            if want_cogs is not None and bool(COGS_RE.search(acct["name"])) != want_cogs:
                continue
            rows.append({"code": code, "name": acct["name"], "amount": _money(amount)})
        return sorted(rows, key=lambda r: r["code"])

    revenue_rows = pl_rows("INCOME")
    cogs_rows = pl_rows("EXPENSE", True)
    opex_rows = pl_rows("EXPENSE", False)
    revenue = _money(sum(r["amount"] for r in revenue_rows))
    cogs = _money(sum(r["amount"] for r in cogs_rows))
    opex = _money(sum(r["amount"] for r in opex_rows))
    net_profit = _money(revenue - cogs - opex)
    profit_and_loss = {
        "revenue": {"rows": revenue_rows, "total": revenue},
        "costOfGoodsSold": {"rows": cogs_rows, "total": cogs},
        "grossProfit": _money(revenue - cogs),
        "operatingExpenses": {"rows": opex_rows, "total": opex},
        "netProfit": net_profit,
    }

    # ---- Balance Sheet (as at end) ----
    closing = _balances(chart, lines, None, end)

    def bs_rows(kind: str) -> list[dict]:
        rows = [
            {"code": c, "name": chart[c]["name"], "amount": _money(v)}
            for c, v in closing.items()
            if chart[c]["type"] == kind and round(v, 2) != 0
        ]
        return sorted(rows, key=lambda r: r["code"])

    asset_rows, liability_rows, equity_rows = bs_rows("ASSET"), bs_rows("LIABILITY"), bs_rows("EQUITY")
    earnings = _money(
        sum(v for c, v in closing.items() if chart[c]["type"] == "INCOME")
        - sum(v for c, v in closing.items() if chart[c]["type"] == "EXPENSE")
    )
    total_assets = _money(sum(r["amount"] for r in asset_rows))
    total_liab = _money(sum(r["amount"] for r in liability_rows))
    total_equity = _money(sum(r["amount"] for r in equity_rows) + earnings)
    balance_check = _money(total_assets - total_liab - total_equity)
    balance_sheet = {
        "asOf": end.isoformat(),
        "assets": {"rows": asset_rows, "total": total_assets},
        "liabilities": {"rows": liability_rows, "total": total_liab},
        "equity": {"rows": equity_rows, "currentEarnings": earnings, "total": total_equity},
        "balanceCheck": balance_check,
    }
    if abs(balance_check) > 0.01:
        warnings.append(f"Balance sheet is out by {balance_check:,.2f}. Check the journal for unbalanced or missing entries.")

    # ---- Cash Flow (indirect) ----
    opening = _balances(chart, lines, None, start - timedelta(days=1))

    def delta(predicate) -> float:
        return sum(
            closing.get(c, 0.0) - opening.get(c, 0.0) for c, a in chart.items() if predicate(a)
        )

    is_cash = lambda a: a["type"] == "ASSET" and CASH_RE.search(a["name"])
    is_fixed = lambda a: a["type"] == "ASSET" and not CASH_RE.search(a["name"]) and FIXED_RE.search(a["name"])
    is_other_asset = lambda a: a["type"] == "ASSET" and not CASH_RE.search(a["name"]) and not FIXED_RE.search(a["name"])
    is_loan = lambda a: a["type"] == "LIABILITY" and LOAN_RE.search(a["name"])
    is_other_liab = lambda a: a["type"] == "LIABILITY" and not LOAN_RE.search(a["name"])

    d_other_assets, d_fixed = delta(is_other_asset), delta(is_fixed)
    d_other_liab, d_loans = delta(is_other_liab), delta(is_loan)
    d_equity = delta(lambda a: a["type"] == "EQUITY")
    operating = _money(net_profit - d_other_assets + d_other_liab)
    investing = _money(-d_fixed)
    financing = _money(d_loans + d_equity)
    net_change = _money(operating + investing + financing)
    opening_cash = _money(sum(opening.get(c, 0.0) for c, a in chart.items() if is_cash(a)))
    closing_cash = _money(sum(closing.get(c, 0.0) for c, a in chart.items() if is_cash(a)))
    actual_change = _money(closing_cash - opening_cash)
    unexplained = _money(actual_change - net_change)
    cash_flow = {
        "operating": {
            "netProfit": net_profit,
            "changeInOtherAssets": _money(-d_other_assets),
            "changeInOtherLiabilities": _money(d_other_liab),
            "total": operating,
        },
        "investing": {"purchaseOfFixedAssets": investing, "total": investing},
        "financing": {"loansAndBorrowings": _money(d_loans), "equityMovement": _money(d_equity), "total": financing},
        "netChangeInCash": net_change,
        "openingCash": opening_cash,
        "closingCash": closing_cash,
        "actualChangeInCash": actual_change,
        "unexplainedDifference": unexplained,
        "method": "Indirect. Accounts are classified by name (cash/bank, fixed assets, loans); depreciation is not adjusted.",
    }
    if abs(unexplained) > 0.01:
        warnings.append(
            f"Cash flow leaves {unexplained:,.2f} unexplained (usually non-cash items such as depreciation, "
            "or accounts whose names do not match the classification)."
        )

    # ---- Trial Balance (closing balances through period end) ----
    trial_rows = []
    for code, balance in sorted(closing.items()):
        account = chart.get(code)
        if not account or abs(balance) < 0.005:
            continue
        debit_nature = account["type"] in {"ASSET", "EXPENSE"}
        debit = _money(max(balance, 0) if debit_nature else max(-balance, 0))
        credit = _money(max(-balance, 0) if debit_nature else max(balance, 0))
        trial_rows.append({"code": code, "name": account["name"], "debit": debit, "credit": credit})
    trial_balance = {
        "asOf": end.isoformat(), "rows": trial_rows,
        "totalDebit": _money(sum(r["debit"] for r in trial_rows)),
        "totalCredit": _money(sum(r["credit"] for r in trial_rows)),
    }
    if abs(trial_balance["totalDebit"] - trial_balance["totalCredit"]) > 0.01:
        warnings.append("Trial Balance does not balance. Review imported or posted journal entries.")

    # ---- General Ledger detail (period lines with account running balances) ----
    running = {code: 0.0 for code in chart}
    general_ledger = []
    ordered_lines = sorted(lines, key=lambda row: (row["date"], str(row.get("voucher_no", "")), str(row["account_code"])))
    for line in ordered_lines:
        code = str(line["account_code"])
        account = chart.get(code)
        if not account:
            continue
        movement = _signed(account["type"], float(line["debit"]), float(line["credit"]))
        running[code] = running.get(code, 0.0) + movement
        if start <= line["date"] <= end:
            general_ledger.append({
                "date": line["date"].isoformat(), "voucherNo": line.get("voucher_no"),
                "accountCode": code, "accountName": account["name"],
                "narration": line.get("narration"), "debit": _money(line["debit"]),
                "credit": _money(line["credit"]), "runningBalance": _money(running[code]),
            })

    return {
        "period": {"start": start.isoformat(), "end": end.isoformat()},
        "profitAndLoss": profit_and_loss,
        "balanceSheet": balance_sheet,
        "cashFlow": cash_flow,
        "trialBalance": trial_balance,
        "generalLedger": general_ledger,
        "warnings": warnings,
    }


def compare_statements(current: dict, previous: dict) -> dict:
    """Variance table plus deterministic commentary lines (numbers computed here)."""
    cur, prev = current["profitAndLoss"], previous["profitAndLoss"]
    metrics = [
        ("Revenue", cur["revenue"]["total"], prev["revenue"]["total"]),
        ("Cost of goods sold", cur["costOfGoodsSold"]["total"], prev["costOfGoodsSold"]["total"]),
        ("Gross profit", cur["grossProfit"], prev["grossProfit"]),
        ("Operating expenses", cur["operatingExpenses"]["total"], prev["operatingExpenses"]["total"]),
        ("Net profit", cur["netProfit"], prev["netProfit"]),
    ]
    variances = []
    for label, now, before in metrics:
        diff = _money(now - before)
        variances.append(
            {
                "metric": label,
                "previous": before,
                "current": now,
                "variance": diff,
                "variancePct": round(diff / abs(before) * 100, 1) if before else None,
            }
        )

    def by_account(pl: dict) -> dict[str, dict]:
        out = {}
        for section in ("revenue", "costOfGoodsSold", "operatingExpenses"):
            for r in pl[section]["rows"]:
                out[r["code"]] = {"name": r["name"], "amount": r["amount"]}
        return out

    a_now, a_prev = by_account(cur), by_account(prev)
    movers = []
    for code in set(a_now) | set(a_prev):
        now = a_now.get(code, {}).get("amount", 0.0)
        before = a_prev.get(code, {}).get("amount", 0.0)
        movers.append(
            {
                "code": code,
                "name": (a_now.get(code) or a_prev.get(code))["name"],
                "previous": before,
                "current": now,
                "variance": _money(now - before),
            }
        )
    movers.sort(key=lambda m: abs(m["variance"]), reverse=True)
    movers = [m for m in movers if m["variance"] != 0][:5]

    lines = []
    for v in variances:
        if v["variance"] == 0:
            lines.append(f"{v['metric']} was unchanged at INR {v['current']:,.2f}.")
            continue
        verb = "rose" if v["variance"] > 0 else "fell"
        pct = f" ({abs(v['variancePct']):.1f}%)" if v["variancePct"] is not None else ""
        lines.append(
            f"{v['metric']} {verb} by INR {abs(v['variance']):,.2f}{pct}, from INR {v['previous']:,.2f} to INR {v['current']:,.2f}."
        )
    for m in movers[:3]:
        verb = "up" if m["variance"] > 0 else "down"
        lines.append(f"Biggest account movement: {m['name']} is {verb} INR {abs(m['variance']):,.2f}.")
    return {"variances": variances, "topMovers": movers, "commentaryLines": lines}


# ---------------------------------------------------------------- import / template


def _parse_date(value) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value or "").strip()
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%d-%b-%Y", "%d %b %Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _num(value) -> Decimal:
    if value is None or str(value).strip() == "":
        return Decimal("0")
    try:
        return Decimal(str(value).replace(",", "").strip())
    except InvalidOperation as exc:
        raise ValueError(f"'{value}' is not a number") from exc


def _headers(sheet) -> tuple[dict[str, int], int]:
    for index, row in enumerate(sheet.iter_rows(min_row=1, max_row=10, values_only=True), start=1):
        names = {str(c or "").strip().lower(): i for i, c in enumerate(row)}
        if names:
            yield_names = {k: v for k, v in names.items() if k}
            if "code" in yield_names or "date" in yield_names:
                return yield_names, index
    raise ValueError(f"Sheet '{sheet.title}' needs a header row.")


def parse_ledger_workbook(content: bytes) -> tuple[list[dict], list[dict]]:
    """Read the 'Accounts' and 'Journal' sheets. Raises ValueError listing problems."""
    workbook = load_workbook(BytesIO(content), read_only=True, data_only=True)
    try:
        names = {n.lower(): n for n in workbook.sheetnames}
        if "accounts" not in names or "journal" not in names:
            raise ValueError("The workbook must contain sheets named 'Accounts' and 'Journal'.")
        problems: list[str] = []

        # Accounts
        sheet = workbook[names["accounts"]]
        cols, header_row = _headers(sheet)
        for need in ("code", "name", "type"):
            if need not in cols:
                raise ValueError(f"Accounts sheet is missing the '{need}' column.")
        accounts, seen = [], set()
        for row_no, row in enumerate(sheet.iter_rows(min_row=header_row + 1, values_only=True), start=header_row + 1):
            if not any(row):
                continue
            code, name, kind = (row[cols[k]] if cols[k] < len(row) else None for k in ("code", "name", "type"))
            if not code or not name:
                problems.append(f"Accounts row {row_no}: code and name are required.")
                continue
            norm = normalise_type(kind)
            if norm is None:
                problems.append(f"Accounts row {row_no}: type '{kind}' must be Asset, Liability, Equity, Income or Expense.")
                continue
            code = str(code).strip()
            if code in seen:
                problems.append(f"Accounts row {row_no}: duplicate code {code}.")
                continue
            seen.add(code)
            accounts.append({"code": code, "name": str(name).strip(), "type": norm})

        # Journal
        sheet = workbook[names["journal"]]
        cols, header_row = _headers(sheet)
        for need in ("date", "voucher no", "account code", "debit", "credit"):
            if need not in cols:
                raise ValueError(f"Journal sheet is missing the '{need}' column.")
        lines, voucher_totals = [], {}
        for row_no, row in enumerate(sheet.iter_rows(min_row=header_row + 1, values_only=True), start=header_row + 1):
            if not any(row):
                continue
            if len(lines) >= MAX_IMPORT_ROWS:
                raise ValueError(f"The journal has more than {MAX_IMPORT_ROWS} lines.")
            get = lambda k: row[cols[k]] if k in cols and cols[k] < len(row) else None
            when = _parse_date(get("date"))
            voucher = str(get("voucher no") or "").strip()
            code = str(get("account code") or "").strip()
            try:
                debit, credit = _num(get("debit")), _num(get("credit"))
            except ValueError as exc:
                problems.append(f"Journal row {row_no}: {exc}.")
                continue
            if when is None:
                problems.append(f"Journal row {row_no}: unreadable date.")
            elif not voucher or not code:
                problems.append(f"Journal row {row_no}: voucher no and account code are required.")
            elif code not in seen:
                problems.append(f"Journal row {row_no}: account code {code} is not in the Accounts sheet.")
            elif debit < 0 or credit < 0 or (debit > 0) == (credit > 0):
                problems.append(f"Journal row {row_no}: enter either a debit or a credit amount (not both, not negative).")
            else:
                lines.append(
                    {
                        "date": when,
                        "voucher_no": voucher,
                        "account_code": code,
                        "narration": (str(get("narration"))[:500] if get("narration") else None),
                        "debit": debit,
                        "credit": credit,
                    }
                )
                d, c = voucher_totals.get(voucher, (Decimal("0"), Decimal("0")))
                voucher_totals[voucher] = (d + debit, c + credit)
        for voucher, (d, c) in voucher_totals.items():
            if abs(d - c) > Decimal("0.01"):
                problems.append(f"Voucher {voucher} is not balanced (debit {d} vs credit {c}).")

        if problems:
            shown = problems[:10]
            more = f" (+{len(problems) - 10} more)" if len(problems) > 10 else ""
            raise ValueError("Ledger import rejected: " + " ".join(shown) + more)
        if not accounts or not lines:
            raise ValueError("The workbook has no accounts or no journal lines.")
        return accounts, lines
    finally:
        workbook.close()


def ledger_template_xlsx() -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Accounts"
    ws.append(["Code", "Name", "Type"])
    for code, name, kind in DEFAULT_CHART:
        ws.append([code, name, kind.title()])
    journal = wb.create_sheet("Journal")
    journal.append(["Date", "Voucher No", "Account Code", "Narration", "Debit", "Credit"])
    journal.append(["2026-04-01", "V-001", "1000", "Owner capital introduced", 500000, 0])
    journal.append(["2026-04-01", "V-001", "3000", "Owner capital introduced", 0, 500000])
    journal.append(["2026-04-10", "V-002", "1000", "Cash sale", 120000, 0])
    journal.append(["2026-04-10", "V-002", "4000", "Cash sale", 0, 120000])
    journal.append(["2026-04-15", "V-003", "5200", "April rent", 30000, 0])
    journal.append(["2026-04-15", "V-003", "1000", "April rent", 0, 30000])
    note = wb.create_sheet("Instructions")
    note.append(["Each voucher must balance (total debit = total credit). Each row has either a debit or a credit."])
    note.append(["Importing REPLACES your existing ledger accounts and journal lines."])
    out = BytesIO()
    wb.save(out)
    return out.getvalue()
