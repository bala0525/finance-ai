"""Accounts Receivable: collection priority, reminder drafts, cash-forecast inputs."""

from __future__ import annotations

from datetime import date, timedelta

STAGES = ["NOT_DUE", "DUE_SOON", "OVERDUE_1_30", "OVERDUE_31_60", "OVERDUE_61_PLUS"]


def stage_for(due: date | None, today: date) -> str:
    if due is None:
        return "NOT_DUE"
    days = (today - due).days
    if days <= -8:
        return "NOT_DUE"
    if days <= 0:
        return "DUE_SOON"
    if days <= 30:
        return "OVERDUE_1_30"
    if days <= 60:
        return "OVERDUE_31_60"
    return "OVERDUE_61_PLUS"


def priority_rows(docs: list[dict], today: date) -> list[dict]:
    """docs: [{id, name, party, invoice_number, amount, due_date}] (unpaid only)."""
    usable = [d for d in docs if d.get("amount") is not None and float(d["amount"]) > 0]
    if not usable:
        return []
    largest = max(float(d["amount"]) for d in usable)
    rows = []
    for d in usable:
        due = d.get("due_date")
        days_overdue = (today - due).days if due else None
        if days_overdue is None:
            urgency = 5.0
        elif days_overdue > 0:
            urgency = min(70.0, 20 + days_overdue * 0.6)
        elif days_overdue >= -7:
            urgency = 10.0
        else:
            urgency = 0.0
        size = 30.0 * float(d["amount"]) / largest
        score = round(min(100.0, urgency + size), 1)

        if days_overdue is None:
            reason = "No due date on the document"
        elif days_overdue > 0:
            reason = f"{days_overdue} days overdue"
        elif days_overdue >= -7:
            reason = f"Due in {-days_overdue} day(s)"
        else:
            reason = "Not yet due"
        reason += f"; {float(d['amount']) / largest * 100:.0f}% of the largest open balance"
        rows.append(
            {
                "documentId": d["id"],
                "documentName": d.get("name"),
                "customer": d.get("party") or "Unknown customer",
                "invoiceNumber": d.get("invoice_number"),
                "amount": round(float(d["amount"]), 2),
                "dueDate": due.isoformat() if due else None,
                "daysOverdue": days_overdue if days_overdue is not None and days_overdue > 0 else 0,
                "stage": stage_for(due, today),
                "priorityScore": score,
                "reason": reason,
            }
        )
    rows.sort(key=lambda r: (-r["priorityScore"], r["documentId"]))
    for rank, row in enumerate(rows, start=1):
        row["rank"] = rank
    return rows


_TEMPLATES = {
    "NOT_DUE": (
        "Upcoming invoice {invoice} ({amount})",
        "Dear {customer},\n\nThis is a courtesy note that invoice {invoice} for {amount} is due on {due}. "
        "Please let us know if you need any document to process the payment.\n\nRegards",
    ),
    "DUE_SOON": (
        "Invoice {invoice} is due shortly",
        "Dear {customer},\n\nInvoice {invoice} for {amount} falls due on {due}. "
        "Kindly arrange the payment on or before the due date.\n\nRegards",
    ),
    "OVERDUE_1_30": (
        "Payment reminder: invoice {invoice}",
        "Dear {customer},\n\nOur records show invoice {invoice} for {amount}, due on {due}, is now overdue. "
        "Please arrange payment at your earliest convenience, or tell us if it has already been paid.\n\nRegards",
    ),
    "OVERDUE_31_60": (
        "Second reminder: invoice {invoice} is overdue",
        "Dear {customer},\n\nInvoice {invoice} for {amount} (due {due}) remains unpaid after our earlier reminder. "
        "Please confirm the payment date this week, or contact us if there is a query on the invoice.\n\nRegards",
    ),
    "OVERDUE_61_PLUS": (
        "Final notice: invoice {invoice} seriously overdue",
        "Dear {customer},\n\nInvoice {invoice} for {amount} (due {due}) is more than 60 days overdue. "
        "Please settle it immediately or call us to agree a payment plan. Further action may follow.\n\nRegards",
    ),
}


def reminder_draft(stage: str, customer: str, invoice: str | None, amount: float, due: date | None) -> dict:
    subject_tpl, body_tpl = _TEMPLATES.get(stage, _TEMPLATES["OVERDUE_1_30"])
    values = {
        "customer": customer or "Customer",
        "invoice": invoice or "(no number)",
        "amount": f"INR {amount:,.2f}",
        "due": due.strftime("%d %b %Y") if due else "the due date",
    }
    return {"subject": subject_tpl.format(**values), "body": body_tpl.format(**values)}


def cash_forecast_weeks(docs: list[dict], today: date, weeks: int = 12, delay_days: int = 0) -> dict:
    """Expected inflows by week from due dates of unpaid receivables."""
    buckets = [0.0] * weeks
    overdue, beyond, undated = 0.0, 0.0, 0.0
    for d in docs:
        amount = d.get("amount")
        if amount is None:
            continue
        amount = float(amount)
        due = d.get("due_date")
        if due is None:
            undated += amount
            continue
        expected = due + timedelta(days=delay_days)
        offset = (expected - today).days
        if offset < 0:
            overdue += amount
            continue
        week = offset // 7
        if week < weeks:
            buckets[week] += amount
        else:
            beyond += amount
    return {
        "weeks": [
            {
                "week": i + 1,
                "startDate": (today + timedelta(days=7 * i)).isoformat(),
                "expectedInflow": round(buckets[i], 2),
            }
            for i in range(weeks)
        ],
        "overdueTimingUnknown": round(overdue, 2),
        "beyondHorizon": round(beyond, 2),
        "noDueDate": round(undated, 2),
        "note": (
            "Based only on due dates of uploaded receivable documents. Overdue amounts have no reliable "
            "collection date and are shown separately."
        ),
    }
