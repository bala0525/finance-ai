"""Documented, rule-based risk scores (0-100) for documents and vendors.

A score is a prioritisation aid for a human reviewer, not proof of fraud. All weights
live in RULE_WEIGHTS so they can be reviewed and tuned in one place.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from statistics import median

RULE_WEIGHTS = {
    "DUPLICATE_FLAG": 40,
    "POSSIBLE_DUPLICATE_INVOICE": 35,
    "UNUSUALLY_HIGH_AMOUNT": 25,
    "JUST_BELOW_APPROVAL_LIMIT": 20,
    "VENDOR_REPEAT_AMOUNT": 15,
    "ROUND_AMOUNT": 10,
    "MISSING_KEY_FIELDS": 10,
    "WEEKEND_INVOICE_DATE": 5,
}

RULE_DESCRIPTIONS = {
    "DUPLICATE_FLAG": "Flagged as a duplicate during invoice extraction.",
    "POSSIBLE_DUPLICATE_INVOICE": "Same vendor, invoice number and amount appears on more than one document.",
    "UNUSUALLY_HIGH_AMOUNT": "Amount is at least 5x the median of the uploaded invoices.",
    "JUST_BELOW_APPROVAL_LIMIT": "Amount sits just under the Finance Manager approval limit.",
    "VENDOR_REPEAT_AMOUNT": "Vendor billed the identical amount three or more times under different invoice numbers.",
    "ROUND_AMOUNT": "Large round-number amount (a multiple of 1,000).",
    "MISSING_KEY_FIELDS": "Vendor name or invoice number is missing.",
    "WEEKEND_INVOICE_DATE": "Invoice dated on a weekend.",
}

HIGH_THRESHOLD = 50
MEDIUM_THRESHOLD = 25


def band_for(score: int) -> str:
    if score >= HIGH_THRESHOLD:
        return "HIGH"
    if score >= MEDIUM_THRESHOLD:
        return "MEDIUM"
    return "LOW"


def _norm(value) -> str:
    return " ".join(str(value or "").lower().split())


def score_documents(docs: list[dict], approval_limit: float | None = None) -> dict:
    """docs: [{id, name, vendor, invoice_number, invoice_date, amount, is_duplicate}]."""
    amounts = [float(d["amount"]) for d in docs if d.get("amount")]
    med = median(amounts) if len(amounts) >= 5 else None

    groups: dict[tuple, list[int]] = defaultdict(list)
    vendor_amounts: dict[tuple, list[dict]] = defaultdict(list)
    for d in docs:
        if d.get("vendor") and d.get("invoice_number") and d.get("amount") is not None:
            groups[(_norm(d["vendor"]), _norm(d["invoice_number"]), round(float(d["amount"]), 2))].append(d["id"])
        if d.get("vendor") and d.get("amount") is not None:
            vendor_amounts[(_norm(d["vendor"]), round(float(d["amount"]), 2))].append(d)

    repeat_ids: set[int] = set()
    for items in vendor_amounts.values():
        distinct = {_norm(i.get("invoice_number")) for i in items}
        if len(items) >= 3 and len(distinct) >= 3:
            repeat_ids.update(i["id"] for i in items)
    possible_dupes = {doc_id for ids in groups.values() if len(ids) > 1 for doc_id in ids}

    scored = {}
    for d in docs:
        rules = []

        def hit(code: str, detail: str | None = None) -> None:
            rules.append(
                {
                    "code": code,
                    "weight": RULE_WEIGHTS[code],
                    "description": RULE_DESCRIPTIONS[code],
                    "detail": detail,
                }
            )

        amount = float(d["amount"]) if d.get("amount") is not None else None
        if d.get("is_duplicate"):
            hit("DUPLICATE_FLAG")
        if d["id"] in possible_dupes:
            hit("POSSIBLE_DUPLICATE_INVOICE")
        if med and amount is not None and amount >= 5 * med:
            hit("UNUSUALLY_HIGH_AMOUNT", f"{amount:,.2f} vs median {med:,.2f}")
        if approval_limit and amount is not None and 0.9 * approval_limit <= amount < approval_limit:
            hit("JUST_BELOW_APPROVAL_LIMIT", f"{amount:,.2f} vs limit {approval_limit:,.2f}")
        if d["id"] in repeat_ids:
            hit("VENDOR_REPEAT_AMOUNT")
        if amount is not None and amount >= 10000 and amount % 1000 == 0:
            hit("ROUND_AMOUNT", f"{amount:,.0f}")
        if not d.get("vendor") or not d.get("invoice_number"):
            hit("MISSING_KEY_FIELDS")
        when = d.get("invoice_date")
        if isinstance(when, date) and when.weekday() >= 5:
            hit("WEEKEND_INVOICE_DATE", when.isoformat())

        score = min(100, sum(r["weight"] for r in rules))
        scored[d["id"]] = {
            "documentId": d["id"],
            "documentName": d.get("name"),
            "vendor": d.get("vendor"),
            "amount": amount,
            "score": score,
            "band": band_for(score),
            "rules": rules,
        }

    vendors: dict[str, dict] = {}
    for item in scored.values():
        key = item["vendor"] or "Unknown vendor"
        entry = vendors.setdefault(key, {"vendor": key, "documentCount": 0, "highDocuments": 0, "maxScore": 0})
        entry["documentCount"] += 1
        entry["maxScore"] = max(entry["maxScore"], item["score"])
        if item["band"] == "HIGH":
            entry["highDocuments"] += 1
    for entry in vendors.values():
        entry["score"] = min(100, entry["maxScore"] + 5 * max(0, entry["highDocuments"] - 1))
        entry["band"] = band_for(entry["score"])
        del entry["maxScore"]

    return {
        "documents": sorted(scored.values(), key=lambda r: (-r["score"], r["documentId"])),
        "vendors": sorted(vendors.values(), key=lambda r: (-r["score"], r["vendor"])),
        "ruleWeights": RULE_WEIGHTS,
        "bands": {"HIGH": f">= {HIGH_THRESHOLD}", "MEDIUM": f">= {MEDIUM_THRESHOLD}", "LOW": f"< {MEDIUM_THRESHOLD}"},
        "note": "Risk scores prioritise review. They are not proof of fraud.",
    }
