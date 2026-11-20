"""Expense policy checks and reimbursement recommendations (recommendation only)."""

from __future__ import annotations

import re
from datetime import date, timedelta

EXPENSE_TYPES = ["Travel", "Meals", "Office", "Software", "Training", "Other"]

# Starting values only; the UI marks them as defaults until an admin edits them.
DEFAULT_POLICIES = {
    "Travel": 50000.0,
    "Meals": 5000.0,
    "Office": 25000.0,
    "Software": 100000.0,
    "Training": 40000.0,
    "Other": 20000.0,
}

_TYPE_KEYWORDS = [
    ("Travel", ("flight", "airline", "hotel", "taxi", "uber", "ola", "cab", "train", "travel", "fuel", "petrol", "irctc")),
    ("Meals", ("restaurant", "cafe", "food", "meal", "swiggy", "zomato", "lunch", "dinner", "catering")),
    ("Software", ("software", "subscription", "saas", "cloud", "license", "licence", "hosting")),
    ("Training", ("training", "course", "workshop", "seminar", "conference", "udemy")),
    ("Office", ("stationery", "office", "supplies", "printer", "furniture")),
]

BLOCKING = {"MISSING_AMOUNT", "DUPLICATE", "FUTURE_DATE", "MISSING_RECEIPT_NUMBER"}
STALE_DAYS = 90


def classify_expense(*texts: str | None) -> str:
    haystack = " ".join(t for t in texts if t).lower()
    for expense_type, words in _TYPE_KEYWORDS:
        if any(re.search(rf"\b{re.escape(w)}", haystack) for w in words):
            return expense_type
    return "Other"


def evaluate_expense(doc: dict, policies: dict[str, dict], today: date) -> dict:
    """doc: {name, vendor, invoice_number, invoice_date, amount, is_duplicate}.

    policies: {type: {"limit": float|None, "receipt_required": bool}}.
    """
    expense_type = classify_expense(doc.get("vendor"), doc.get("name"))
    policy = policies.get(expense_type) or policies.get("Other") or {"limit": None, "receipt_required": True}
    amount = doc.get("amount")
    amount = float(amount) if amount is not None else None
    violations: list[dict] = []

    def add(code: str, message: str, severity: str) -> None:
        violations.append({"code": code, "message": message, "severity": severity})

    if amount is None or amount <= 0:
        add("MISSING_AMOUNT", "No valid claim amount could be read from the document.", "HIGH")
    if doc.get("is_duplicate"):
        add("DUPLICATE", "This looks like a duplicate of an earlier claim.", "HIGH")
    if policy.get("receipt_required") and not (doc.get("invoice_number") or "").strip():
        add("MISSING_RECEIPT_NUMBER", "Receipt / bill number is required but was not found.", "HIGH")

    when = doc.get("invoice_date")
    if when is None:
        add("MISSING_DATE", "Expense date was not found.", "LOW")
    elif when > today:
        add("FUTURE_DATE", "Expense date is in the future.", "HIGH")
    elif when < today - timedelta(days=STALE_DAYS):
        add("STALE_CLAIM", f"Claim is older than {STALE_DAYS} days.", "LOW")

    limit = policy.get("limit")
    if amount is not None and limit is not None and amount > float(limit):
        add(
            "OVER_LIMIT",
            f"{expense_type} claim of {amount:,.2f} exceeds the policy limit of {float(limit):,.2f}.",
            "MEDIUM",
        )

    codes = {v["code"] for v in violations}
    if codes & BLOCKING:
        decision, allowed = "REJECT", 0.0
        reasons = [v["message"] for v in violations if v["code"] in BLOCKING]
    elif "OVER_LIMIT" in codes:
        decision, allowed = "PARTIAL", float(limit)
        reasons = [v["message"] for v in violations if v["code"] == "OVER_LIMIT"]
    else:
        decision, allowed = "APPROVE", amount or 0.0
        reasons = ["Within policy."] if not violations else [v["message"] for v in violations]

    return {
        "expenseType": expense_type,
        "violations": violations,
        "recommendation": {
            "decision": decision,
            "allowedAmount": round(allowed, 2),
            "reasons": reasons,
            "note": "Recommendation only. A person must confirm the decision.",
        },
    }
