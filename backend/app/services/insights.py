"""Management insights for the Finance Analyst.

Every insight is a deterministic rule over the user's uploaded documents. Each one
states its numbers and the rule that produced it; none comes from a language model.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta

from app.services.analysis import month_key, monthly_totals

LOW_CONFIDENCE = 0.75
SEVERITY_ORDER = {"ACTION": 0, "WATCH": 1, "INFO": 2}


def _inr(value: float) -> str:
    return f"INR {value:,.2f}"


def _open(doc: dict) -> bool:
    return doc.get("status") != "PAID" and doc.get("review_status") != "REJECTED"


def build_insights(docs: list[dict], today: date) -> dict:
    """docs: [{id, name, kind (AP|AR|EXPENSE), vendor, amount, date, due_date, status,
    review_status, validation_status, is_duplicate, confidence}]."""
    if not docs:
        raise ValueError("Insufficient data: upload invoices, receivables or expense documents first.")

    insights: list[dict] = []

    def add(code, severity, title, message, metrics=None):
        insights.append({"code": code, "severity": severity, "title": title, "message": message, "metrics": metrics or {}})

    spend_docs = [d for d in docs if d["kind"] in ("AP", "EXPENSE") and d.get("amount") and d.get("date")]
    payables = [d for d in docs if d["kind"] == "AP" and d.get("amount") is not None and _open(d) and d.get("validation_status") == "VALID"]
    receivables = [d for d in docs if d["kind"] == "AR" and d.get("amount") is not None and _open(d)]

    # 1. Spend trend: last two complete months
    monthly = monthly_totals([{"date": d["date"], "amount": d["amount"]} for d in spend_docs])
    complete = [k for k in sorted(monthly) if k < month_key(today)]
    if len(complete) >= 2:
        last, prev = complete[-1], complete[-2]
        now_v, before_v = monthly[last], monthly[prev]
        if before_v > 0:
            pct = (now_v - before_v) / before_v * 100
            sev = "WATCH" if pct >= 20 else "INFO"
            direction = "rose" if pct > 0 else "fell" if pct < 0 else "was flat"
            add("SPEND_TREND", sev, "Spending trend",
                f"Spend (payables and expenses) {direction} {abs(pct):.1f}% in {last} versus {prev}: {_inr(before_v)} to {_inr(now_v)}.",
                {"month": last, "previousMonth": prev, "current": round(now_v, 2), "previous": round(before_v, 2), "changePct": round(pct, 1)})

    # 2. Vendor concentration
    totals: dict[str, float] = defaultdict(float)
    for d in spend_docs:
        if d.get("vendor"):
            totals[d["vendor"]] += d["amount"]
    grand = sum(totals.values())
    if len(spend_docs) >= 3 and grand > 0 and totals:
        vendor, amount = max(totals.items(), key=lambda kv: kv[1])
        share = amount / grand * 100
        add("VENDOR_CONCENTRATION", "WATCH" if share > 40 else "INFO", "Vendor concentration",
            f"{vendor} accounts for {share:.1f}% of spend ({_inr(amount)} of {_inr(grand)}).",
            {"vendor": vendor, "sharePct": round(share, 1), "amount": round(amount, 2)})

    # 3. Overdue receivables
    open_ar = sum(d["amount"] for d in receivables)
    if receivables and open_ar > 0:
        overdue = [d for d in receivables if d.get("due_date") and d["due_date"] < today]
        overdue_amt = sum(d["amount"] for d in overdue)
        share = overdue_amt / open_ar * 100
        sev = "ACTION" if share > 30 else "WATCH" if overdue else "INFO"
        add("OVERDUE_RECEIVABLES", sev, "Overdue receivables",
            f"{len(overdue)} of {len(receivables)} open receivables are overdue, {_inr(overdue_amt)} ({share:.1f}% of the {_inr(open_ar)} open balance).",
            {"overdueCount": len(overdue), "overdueAmount": round(overdue_amt, 2), "openBalance": round(open_ar, 2), "overduePct": round(share, 1)})

    # 4. Payables falling due soon
    horizon = today + timedelta(days=14)
    due_soon = [d for d in payables if d.get("review_status") == "APPROVED" and d.get("due_date") and today <= d["due_date"] <= horizon]
    if due_soon:
        amt = sum(d["amount"] for d in due_soon)
        add("PAYABLES_DUE_SOON", "WATCH", "Payables due in 14 days",
            f"{len(due_soon)} approved invoice(s) totalling {_inr(amt)} fall due by {horizon.isoformat()}. Plan the payment batch.",
            {"count": len(due_soon), "amount": round(amt, 2)})

    # 5. Approval backlog
    backlog = [d for d in docs if d.get("review_status") == "READY_FOR_REVIEW"]
    if backlog:
        dated = [d["date"] for d in backlog if d.get("date")]
        oldest = (today - min(dated)).days if dated else None
        amt = sum(d["amount"] for d in backlog if d.get("amount"))
        sev = "WATCH" if len(backlog) >= 5 or (oldest or 0) > 14 else "INFO"
        extra = f", oldest waiting {oldest} days" if oldest is not None else ""
        add("APPROVAL_BACKLOG", sev, "Approval backlog",
            f"{len(backlog)} document(s) worth {_inr(amt)} are waiting for review{extra}.",
            {"count": len(backlog), "amount": round(amt, 2), "oldestDays": oldest})

    # 6. Data quality
    low = [d for d in docs if d.get("confidence") is not None and d["confidence"] < LOW_CONFIDENCE]
    invalid = [d for d in docs if d.get("validation_status") in ("INVALID", "ERROR")]
    dupes = [d for d in docs if d.get("is_duplicate") or d.get("validation_status") == "DUPLICATE"]
    if low or invalid or dupes:
        add("DATA_QUALITY", "WATCH", "Data quality",
            f"{len(invalid)} invalid, {len(dupes)} duplicate and {len(low)} low-confidence document(s). Fix these before relying on totals.",
            {"invalid": len(invalid), "duplicates": len(dupes), "lowConfidence": len(low)})

    # 7. Largest payables / expenses
    biggest = sorted(spend_docs, key=lambda d: d["amount"], reverse=True)[:3]
    if biggest:
        lines = "; ".join(f"{d.get('vendor') or d['name']} {_inr(d['amount'])}" for d in biggest)
        add("LARGEST_ITEMS", "INFO", "Largest items", f"Biggest payables / expenses: {lines}.",
            {"items": [{"documentId": d["id"], "vendor": d.get("vendor"), "amount": round(d["amount"], 2)} for d in biggest]})

    # 8. Net working-capital position
    open_ap = sum(d["amount"] for d in payables)
    if receivables or payables:
        net = open_ar - open_ap
        add("NET_POSITION", "WATCH" if net < 0 else "INFO", "Receivables vs payables",
            f"Open receivables {_inr(open_ar)} against open valid payables {_inr(open_ap)}: net {_inr(net)}.",
            {"openReceivables": round(open_ar, 2), "openPayables": round(open_ap, 2), "net": round(net, 2)})

    insights.sort(key=lambda i: SEVERITY_ORDER[i["severity"]])
    return {
        "insights": insights,
        "documentCount": len(docs),
        "asOf": today.isoformat(),
        "note": "Each insight is a fixed rule over your uploaded documents. Nothing here is predicted or guessed.",
    }
