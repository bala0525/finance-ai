"""Turn a reconciliation run's unmatched items into trackable exception cases."""

from __future__ import annotations

REASON_LABELS = {
    "AMBIGUOUS_MATCH": "More than one possible match. Choose the right one manually.",
    "NO_EXACT_AMOUNT_AND_REFERENCE_OR_DESCRIPTION_MATCH": "In the cashbook but not found on the bank statement.",
    "NO_MATCHING_CASHBOOK_TRANSACTION": "On the bank statement but not recorded in the cashbook.",
}


def item_key(item: dict) -> str:
    """Stable key for one unmatched transaction (source, sheet row, side, amount)."""
    return f"{item.get('source', '?')}:{item.get('row', '?')}:{item.get('direction', '?')}:{float(item.get('amount', 0)):.2f}"


def flatten_exceptions(results: dict, resolutions: dict[str, dict]) -> list[dict]:
    """resolutions: {item_key: {status, note, resolvedBy, resolvedAt}}."""
    rows = []
    for side, items in (
        ("CASHBOOK", results.get("unmatchedCashbook", [])),
        ("BANK_STATEMENT", results.get("unmatchedBankStatement", [])),
    ):
        for item in items:
            key = item_key(item)
            resolution = resolutions.get(key)
            rows.append(
                {
                    "itemKey": key,
                    "side": side,
                    "row": item.get("row"),
                    "date": item.get("date"),
                    "description": item.get("description"),
                    "reference": item.get("reference"),
                    "direction": item.get("direction"),
                    "amount": float(item.get("amount", 0)),
                    "reason": item.get("reason"),
                    "reasonText": REASON_LABELS.get(item.get("reason"), item.get("reason")),
                    "status": resolution["status"] if resolution else "OPEN",
                    "note": resolution.get("note") if resolution else None,
                    "resolvedAt": resolution.get("resolvedAt") if resolution else None,
                }
            )
    return rows


def statement_totals(results: dict, exceptions: list[dict]) -> dict:
    matched = results.get("matched", [])
    matched_total = round(sum(float(m["cashbook"]["amount"]) for m in matched), 2)
    open_cash = [e for e in exceptions if e["side"] == "CASHBOOK" and e["status"] == "OPEN"]
    open_bank = [e for e in exceptions if e["side"] == "BANK_STATEMENT" and e["status"] == "OPEN"]
    closed = [e for e in exceptions if e["status"] != "OPEN"]
    return {
        "matchedCount": len(matched),
        "matchedTotal": matched_total,
        "openCashbookCount": len(open_cash),
        "openCashbookTotal": round(sum(e["amount"] for e in open_cash), 2),
        "openBankCount": len(open_bank),
        "openBankTotal": round(sum(e["amount"] for e in open_bank), 2),
        "resolvedCount": len([e for e in closed if e["status"] == "RESOLVED"]),
        "writtenOffCount": len([e for e in closed if e["status"] == "WRITTEN_OFF"]),
        "writtenOffTotal": round(sum(e["amount"] for e in closed if e["status"] == "WRITTEN_OFF"), 2),
    }
