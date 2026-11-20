"""Unit tests for the pure workflow calculation services (no DB, no network)."""

from datetime import date
from decimal import Decimal
from io import BytesIO

import pytest
from openpyxl import Workbook, load_workbook

from app.services import analysis, coding, confidence, exports, expense_policy, fraud_scoring
from app.services import insights, receivables, recon_exceptions, statements

TODAY = date(2026, 11, 2)


# ----------------------------------------------------------------- confidence
def test_confidence_complete_invoice_is_high():
    fields = dict(vendor_name="Acme", invoice_number="A-1", invoice_date=date(2026, 10, 1),
                  due_date=date(2026, 10, 31), subtotal=100, tax_amount=18, total_amount=118)
    score, per_field, reasons = confidence.compute_extraction_confidence(fields, [])
    assert score == 1.0 and not reasons and all(v == 1.0 for v in per_field.values())


def test_confidence_drops_for_missing_and_arithmetic_mismatch():
    fields = dict(vendor_name="Acme", invoice_number=None, invoice_date=date(2026, 10, 1),
                  due_date=date(2026, 9, 1), subtotal=100, tax_amount=18, total_amount=500)
    score, per_field, reasons = confidence.compute_extraction_confidence(fields, ["x"])
    assert score < confidence.LOW_CONFIDENCE_THRESHOLD
    assert per_field["invoice_number"] == 0.0 and per_field["total_amount"] <= 0.3
    assert any("does not equal" in r for r in reasons) and any("before the invoice" in r for r in reasons)


def test_confidence_blends_model_value_and_clamps():
    fields = dict(vendor_name="A", invoice_number="1", invoice_date=date(2026, 1, 1),
                  due_date=date(2026, 2, 1), subtotal=1, tax_amount=0, total_amount=1)
    assert confidence.compute_extraction_confidence(fields, [], 0.5)[0] == 0.8
    assert confidence.compute_extraction_confidence(fields, [], 9)[0] == 1.0


# --------------------------------------------------------------------- coding
CHART = [{"code": c, "name": n, "type": t} for c, n, t in coding.DEFAULT_CHART]


def test_coding_keyword_maps_to_existing_account_only():
    hit = coding.suggest_account_by_keywords("Uber India cab ride", CHART)
    assert hit["code"] == "5600" and hit["source"] == "KEYWORD"
    assert coding.suggest_account_by_keywords("Uber cab", [a for a in CHART if a["code"] != "5600"]) is None
    assert coding.suggest_account_by_keywords("zzz unknown vendor", CHART) is None


def test_coding_ignores_non_codeable_account_types():
    only_income = [a for a in CHART if a["type"] == "INCOME"]
    assert coding.suggest_account_by_keywords("office rent", only_income) is None


# ------------------------------------------------------------------- analysis
ROWS = [
    {"date": date(2026, 8, 5), "amount": 100, "category": "Travel", "vendor": "A"},
    {"date": date(2026, 9, 5), "amount": 150, "category": "Travel", "vendor": "A"},
    {"date": date(2026, 9, 9), "amount": 40, "category": "Office", "vendor": "B"},
    {"date": date(2026, 10, 2), "amount": 300, "category": "Travel", "vendor": "A"},
]


def test_variance_period_vs_period():
    result = analysis.variance_analysis(ROWS, (date(2026, 9, 1), date(2026, 9, 30)), base=(date(2026, 8, 1), date(2026, 8, 31)))
    travel = next(r for r in result["lines"] if r["group"] == "Travel")
    assert travel["variance"] == 50 and travel["variancePct"] == 50.0
    office = next(r for r in result["lines"] if r["group"] == "Office")
    assert office["variancePct"] is None  # no base to divide by
    assert result["totals"]["variance"] == 90


def test_variance_vs_budget_and_validation():
    result = analysis.variance_analysis(ROWS, (date(2026, 9, 1), date(2026, 9, 30)), budget={"Travel": 200, "Office": 10})
    assert result["basis"] == "BUDGET" and result["totals"]["reference"] == 210
    with pytest.raises(ValueError):
        analysis.variance_analysis(ROWS, (date(2026, 9, 1), date(2026, 9, 30)))
    with pytest.raises(ValueError):
        analysis.variance_analysis(ROWS, (date(2026, 9, 30), date(2026, 9, 1)), budget={"x": 1})


def test_monthly_totals_fills_gaps():
    rows = [{"date": date(2026, 1, 3), "amount": 10}, {"date": date(2026, 3, 3), "amount": 5}]
    assert analysis.monthly_totals(rows) == {"2026-01": 10.0, "2026-02": 0.0, "2026-03": 5.0}


def test_forecast_methods_and_data_requirements():
    monthly = {"2026-01": 100.0, "2026-02": 200.0, "2026-03": 300.0}
    trend = analysis.forecast_series(monthly, 2, "linear_trend")
    assert [f["value"] for f in trend["forecast"]] == [400.0, 500.0]
    assert trend["forecast"][0]["period"] == "2026-04" and trend["warnings"]
    avg = analysis.forecast_series(monthly, 1, "moving_average")
    assert avg["forecast"][0]["value"] == 200.0
    with pytest.raises(ValueError, match="Insufficient data"):
        analysis.forecast_series({"2026-01": 1.0, "2026-02": 2.0}, 1, "moving_average")
    assert analysis.next_month_key("2026-12") == "2027-01"


def test_scenario_changes_and_collection_delay():
    recs = [{"amount": 1000, "due_date": date(2026, 11, 9)}, {"amount": 500, "due_date": date(2026, 10, 1)}]
    result = analysis.scenario_analysis(10000, 6000, recs, 10, -5, 14, today=TODAY)
    assert result["scenario"]["revenue"] == 11000 and result["scenario"]["expenses"] == 5700
    assert result["scenario"]["net"] == 5300 and result["base"]["net"] == 4000
    assert result["weeklyInflows"][1]["base"] == 1000 and result["weeklyInflows"][3]["scenario"] == 1000
    with pytest.raises(ValueError):
        analysis.scenario_analysis(1, 1, [], revenue_change_pct=-150)


# ---------------------------------------------------------------- receivables
def test_collection_priority_orders_by_urgency_and_size():
    docs = [
        {"id": 1, "party": "X", "amount": 1000, "due_date": date(2026, 8, 1)},   # 93 days overdue
        {"id": 2, "party": "Y", "amount": 100000, "due_date": date(2026, 12, 30)},  # big, not due
        {"id": 3, "party": "Z", "amount": 500, "due_date": date(2026, 10, 25)},    # 8 days overdue
    ]
    rows = receivables.priority_rows(docs, TODAY)
    assert [r["documentId"] for r in rows] == [1, 3, 2] or rows[0]["priorityScore"] >= rows[-1]["priorityScore"]
    assert rows[0]["rank"] == 1 and {r["documentId"]: r["stage"] for r in rows}[1] == "OVERDUE_61_PLUS"
    assert receivables.stage_for(date(2026, 11, 5), TODAY) == "DUE_SOON"
    assert receivables.stage_for(date(2026, 10, 20), TODAY) == "OVERDUE_1_30"
    assert receivables.priority_rows([], TODAY) == []


def test_reminder_draft_and_cash_forecast_buckets():
    draft = receivables.reminder_draft("OVERDUE_31_60", "Acme", "INV-9", 1234.5, date(2026, 9, 1))
    assert "INV-9" in draft["subject"] and "1,234.50" in draft["body"]
    fc = receivables.cash_forecast_weeks(
        [{"amount": 100, "due_date": date(2026, 11, 3)}, {"amount": 50, "due_date": date(2026, 9, 1)},
         {"amount": 70, "due_date": date(2027, 6, 1)}, {"amount": 5, "due_date": None}], TODAY)
    assert fc["weeks"][0]["expectedInflow"] == 100 and fc["overdueTimingUnknown"] == 50
    assert fc["beyondHorizon"] == 70 and fc["noDueDate"] == 5


# ------------------------------------------------------------- expense policy
POLICIES = {"Travel": {"limit": 1000.0, "receipt_required": True}, "Other": {"limit": 500.0, "receipt_required": True}}


def test_expense_over_limit_is_partial_and_clean_is_approved():
    over = expense_policy.evaluate_expense(
        {"name": "flight.pdf", "vendor": "IndiGo Airlines", "invoice_number": "T1", "invoice_date": date(2026, 10, 20), "amount": 1500}, POLICIES, TODAY)
    assert over["expenseType"] == "Travel" and over["recommendation"]["decision"] == "PARTIAL"
    assert over["recommendation"]["allowedAmount"] == 1000.0
    ok = expense_policy.evaluate_expense(
        {"name": "x", "vendor": "Cab", "invoice_number": "T2", "invoice_date": date(2026, 10, 20), "amount": 300}, POLICIES, TODAY)
    assert ok["recommendation"]["decision"] == "APPROVE"


def test_expense_blocking_violations_reject():
    for doc, code in [
        ({"vendor": "Cab", "invoice_number": None, "invoice_date": date(2026, 10, 1), "amount": 10}, "MISSING_RECEIPT_NUMBER"),
        ({"vendor": "Cab", "invoice_number": "1", "invoice_date": date(2027, 1, 1), "amount": 10}, "FUTURE_DATE"),
        ({"vendor": "Cab", "invoice_number": "1", "invoice_date": date(2026, 10, 1), "amount": None}, "MISSING_AMOUNT"),
        ({"vendor": "Cab", "invoice_number": "1", "invoice_date": date(2026, 10, 1), "amount": 10, "is_duplicate": True}, "DUPLICATE"),
    ]:
        result = expense_policy.evaluate_expense({"name": "n", **doc}, POLICIES, TODAY)
        assert code in {v["code"] for v in result["violations"]}
        assert result["recommendation"]["decision"] == "REJECT"


# --------------------------------------------------------------- fraud scoring
def test_fraud_scoring_rules_and_bands():
    docs = [
        {"id": 1, "name": "a", "vendor": "V", "invoice_number": "1", "invoice_date": date(2026, 10, 3), "amount": 50000, "is_duplicate": True},
        {"id": 2, "name": "b", "vendor": "V", "invoice_number": "1", "invoice_date": date(2026, 10, 5), "amount": 50000, "is_duplicate": False},
        {"id": 3, "name": "c", "vendor": "W", "invoice_number": "9", "invoice_date": date(2026, 10, 6), "amount": 990, "is_duplicate": False},
        {"id": 4, "name": "d", "vendor": "W", "invoice_number": "8", "invoice_date": date(2026, 10, 7), "amount": 1000, "is_duplicate": False},
        {"id": 5, "name": "e", "vendor": "W", "invoice_number": "7", "invoice_date": date(2026, 10, 8), "amount": 1100, "is_duplicate": False},
        {"id": 6, "name": "f", "vendor": "W", "invoice_number": "6", "invoice_date": date(2026, 10, 9), "amount": 1200, "is_duplicate": False},
    ]
    result = fraud_scoring.score_documents(docs, approval_limit=1000)
    by_id = {d["documentId"]: d for d in result["documents"]}
    codes1 = {r["code"] for r in by_id[1]["rules"]}
    assert {"DUPLICATE_FLAG", "POSSIBLE_DUPLICATE_INVOICE", "UNUSUALLY_HIGH_AMOUNT", "ROUND_AMOUNT", "WEEKEND_INVOICE_DATE"} <= codes1
    assert by_id[1]["band"] == "HIGH" and by_id[1]["score"] <= 100
    assert "JUST_BELOW_APPROVAL_LIMIT" in {r["code"] for r in by_id[3]["rules"]}
    assert result["documents"][0]["score"] >= result["documents"][-1]["score"]
    assert {v["vendor"] for v in result["vendors"]} == {"V", "W"}
    assert fraud_scoring.band_for(10) == "LOW" and fraud_scoring.band_for(30) == "MEDIUM"


# ------------------------------------------------------------------ statements
ACCOUNTS = [{"code": c, "name": n, "type": t} for c, n, t in coding.DEFAULT_CHART]


def _line(d, v, code, debit=0, credit=0):
    return {"date": d, "voucher_no": v, "account_code": code, "debit": debit, "credit": credit}


LINES = [
    _line(date(2026, 4, 1), "V1", "1000", 500000), _line(date(2026, 4, 1), "V1", "3000", 0, 500000),
    _line(date(2026, 4, 10), "V2", "1000", 120000), _line(date(2026, 4, 10), "V2", "4000", 0, 120000),
    _line(date(2026, 4, 15), "V3", "5200", 30000), _line(date(2026, 4, 15), "V3", "1000", 0, 30000),
    _line(date(2026, 5, 3), "V4", "1500", 200000), _line(date(2026, 5, 3), "V4", "1000", 0, 200000),
    _line(date(2026, 5, 20), "V5", "1100", 80000), _line(date(2026, 5, 20), "V5", "4000", 0, 80000),
]


def test_statements_profit_balance_and_cash_flow_tie_out():
    april = statements.build_statements(ACCOUNTS, LINES, date(2026, 4, 1), date(2026, 4, 30))
    assert april["profitAndLoss"]["revenue"]["total"] == 120000
    assert april["profitAndLoss"]["netProfit"] == 90000
    assert april["balanceSheet"]["balanceCheck"] == 0
    assert april["cashFlow"]["closingCash"] == 590000 and april["cashFlow"]["unexplainedDifference"] == 0

    may = statements.build_statements(ACCOUNTS, LINES, date(2026, 5, 1), date(2026, 5, 31))
    assert may["profitAndLoss"]["netProfit"] == 80000
    cf = may["cashFlow"]
    assert cf["operating"]["total"] == 0          # 80,000 profit - 80,000 new receivable
    assert cf["investing"]["total"] == -200000
    assert cf["actualChangeInCash"] == -200000 and cf["unexplainedDifference"] == 0
    assert may["balanceSheet"]["balanceCheck"] == 0

    comparison = statements.compare_statements(may, april)
    net = next(v for v in comparison["variances"] if v["metric"] == "Net profit")
    assert net["variance"] == -10000 and "Net profit fell" in " ".join(comparison["commentaryLines"])


def test_statements_warn_on_unknown_accounts_and_bad_period():
    lines = LINES + [_line(date(2026, 4, 2), "V9", "9999", 5)]
    result = statements.build_statements(ACCOUNTS, lines, date(2026, 4, 1), date(2026, 4, 30))
    assert any("missing from the chart" in w for w in result["warnings"])
    with pytest.raises(ValueError):
        statements.build_statements(ACCOUNTS, LINES, date(2026, 5, 1), date(2026, 4, 1))


def test_ledger_template_roundtrip_and_rejections():
    accounts, lines = statements.parse_ledger_workbook(statements.ledger_template_xlsx())
    assert len(accounts) == len(coding.DEFAULT_CHART) and len(lines) == 6
    assert sum(l["debit"] for l in lines) == sum(l["credit"] for l in lines)

    wb = Workbook(); ws = wb.active; ws.title = "Accounts"
    ws.append(["Code", "Name", "Type"]); ws.append(["1000", "Cash", "Asset"]); ws.append(["4000", "Sales", "Income"])
    j = wb.create_sheet("Journal"); j.append(["Date", "Voucher No", "Account Code", "Narration", "Debit", "Credit"])
    j.append(["2026-04-01", "V1", "1000", "x", 100, 0]); j.append(["2026-04-01", "V1", "4000", "x", 0, 90])
    buffer = BytesIO(); wb.save(buffer)
    with pytest.raises(ValueError, match="not balanced"):
        statements.parse_ledger_workbook(buffer.getvalue())

    wb2 = Workbook(); wb2.active.title = "Other"; b2 = BytesIO(); wb2.save(b2)
    with pytest.raises(ValueError, match="Accounts"):
        statements.parse_ledger_workbook(b2.getvalue())


# ---------------------------------------------------------------- recon + export
RESULTS = {
    "matched": [{"cashbook": {"row": 2, "amount": 100.0, "date": "2026-10-01", "description": "a"},
                 "bankStatement": {"row": 5}, "matchMethod": "AMOUNT_AND_REFERENCE"}],
    "unmatchedCashbook": [{"source": "CASHBOOK", "row": 3, "direction": "DEBIT", "amount": 40.0, "description": "late cheque",
                           "reason": "NO_EXACT_AMOUNT_AND_REFERENCE_OR_DESCRIPTION_MATCH", "date": "2026-10-02", "reference": None}],
    "unmatchedBankStatement": [{"source": "BANK_STATEMENT", "row": 7, "direction": "CREDIT", "amount": 15.5, "description": "bank fee",
                                "reason": "NO_MATCHING_CASHBOOK_TRANSACTION", "date": "2026-10-03", "reference": None}],
}


def test_recon_exceptions_resolution_and_statement_totals():
    key = recon_exceptions.item_key(RESULTS["unmatchedBankStatement"][0])
    rows = recon_exceptions.flatten_exceptions(RESULTS, {key: {"status": "WRITTEN_OFF", "note": "bank fee"}})
    assert {r["status"] for r in rows} == {"OPEN", "WRITTEN_OFF"}
    totals = recon_exceptions.statement_totals(RESULTS, rows)
    assert totals["openCashbookTotal"] == 40.0 and totals["openBankCount"] == 0
    assert totals["writtenOffTotal"] == 15.5 and totals["matchedTotal"] == 100.0
    data = exports.reconciliation_statement_xlsx("rec.xlsx", {"matchingPolicy": "p"}, totals, rows, RESULTS["matched"])
    assert load_workbook(BytesIO(data)).sheetnames == ["Statement", "Exceptions", "Matched"]


def test_exports_neutralise_formula_injection_and_build():
    assert exports._safe("=SUM(A1)") == "'=SUM(A1)" and exports._safe(5) == 5
    batch = {"name": "=evil", "paymentDate": "2026-11-05", "status": "DRAFT", "itemCount": 1, "totalAmount": 10}
    items = [{"vendor": "V", "invoiceNumber": "1", "invoiceDate": None, "dueDate": None, "accountCode": "5200", "amount": 10, "documentName": "d"}]
    wb = load_workbook(BytesIO(exports.payment_batch_xlsx(batch, items)))
    assert wb["Batch"]["B1"].value == "'=evil" and wb["Invoices"].max_row == 2
    st = statements.build_statements(ACCOUNTS, LINES, date(2026, 4, 1), date(2026, 4, 30))
    prev = statements.build_statements(ACCOUNTS, LINES, date(2026, 3, 1), date(2026, 3, 31))
    cmp = statements.compare_statements(st, prev)
    sheets = load_workbook(BytesIO(exports.statements_xlsx(st, cmp, cmp["commentaryLines"]))).sheetnames
    assert sheets == ["Summary", "P&L", "Balance Sheet", "Cash Flow", "Trial Balance", "General Ledger", "Variance", "Commentary"]


# -------------------------------------------------------------------- insights
def _d(i, kind, amount, when, **kw):
    base = {"id": i, "name": f"d{i}", "kind": kind, "vendor": kw.pop("vendor", "V"), "amount": amount, "date": when,
            "due_date": kw.pop("due", None), "status": "Processed", "review_status": kw.pop("review", "APPROVED"),
            "validation_status": kw.pop("valid", "VALID"), "is_duplicate": False, "confidence": kw.pop("conf", 0.9)}
    base.update(kw)
    return base


def test_insights_rules_fire_with_numbers():
    docs = [
        _d(1, "AP", 1000, date(2026, 9, 10), vendor="Acme"),
        _d(2, "AP", 1500, date(2026, 10, 10), vendor="Acme", due=date(2026, 11, 8)),
        _d(3, "EXPENSE", 200, date(2026, 10, 12), vendor="Cab"),
        _d(4, "AR", 5000, date(2026, 8, 1), due=date(2026, 9, 1), vendor="Cust"),
        _d(5, "AR", 1000, date(2026, 10, 1), due=date(2026, 12, 1), vendor="Cust2"),
        _d(6, "AP", 300, date(2026, 10, 20), review="READY_FOR_REVIEW", conf=0.5, valid="INVALID"),
    ]
    result = insights.build_insights(docs, TODAY)
    by = {i["code"]: i for i in result["insights"]}
    assert by["SPEND_TREND"]["metrics"]["changePct"] == 100.0 and by["SPEND_TREND"]["severity"] == "WATCH"
    assert by["VENDOR_CONCENTRATION"]["metrics"]["vendor"] == "Acme"
    assert by["OVERDUE_RECEIVABLES"]["severity"] == "ACTION" and by["OVERDUE_RECEIVABLES"]["metrics"]["overdueAmount"] == 5000
    assert by["PAYABLES_DUE_SOON"]["metrics"]["count"] == 1
    assert by["APPROVAL_BACKLOG"]["metrics"]["count"] == 1
    assert by["DATA_QUALITY"]["metrics"] == {"invalid": 1, "duplicates": 0, "lowConfidence": 1}
    assert by["NET_POSITION"]["metrics"]["openReceivables"] == 6000
    assert [i["severity"] for i in result["insights"]] == sorted((i["severity"] for i in result["insights"]), key={"ACTION": 0, "WATCH": 1, "INFO": 2}.get)


def test_insights_need_data_and_skip_rules_without_inputs():
    with pytest.raises(ValueError, match="Insufficient data"):
        insights.build_insights([], TODAY)
    only_ar = insights.build_insights([_d(1, "AR", 100, date(2026, 10, 1), due=date(2026, 12, 1))], TODAY)
    codes = {i["code"] for i in only_ar["insights"]}
    assert "SPEND_TREND" not in codes and "VENDOR_CONCENTRATION" not in codes and "OVERDUE_RECEIVABLES" in codes
