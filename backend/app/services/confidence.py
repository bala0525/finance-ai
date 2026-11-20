"""Extraction confidence for invoice fields.

Deterministic checks (field presence, subtotal + tax = total, date order, validation
errors) optionally blended with the model's self-reported confidence. Pure functions:
no database, no network.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation

LOW_CONFIDENCE_THRESHOLD = 0.75

FIELD_WEIGHTS = {
    "vendor_name": 0.20,
    "invoice_number": 0.20,
    "invoice_date": 0.15,
    "due_date": 0.10,
    "subtotal": 0.10,
    "tax_amount": 0.05,
    "total_amount": 0.20,
}


def _dec(value) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def compute_extraction_confidence(
    fields: dict,
    validation_errors: list | None = None,
    model_confidence: float | None = None,
) -> tuple[float, dict, list[str]]:
    """Return ``(overall 0-1, per-field scores, human-readable reasons)``."""
    per_field: dict[str, float] = {}
    reasons: list[str] = []

    for key in FIELD_WEIGHTS:
        value = fields.get(key)
        present = value is not None and str(value).strip() != ""
        per_field[key] = 1.0 if present else 0.0
        if not present:
            reasons.append(f"{key.replace('_', ' ')} was not found")

    overall = sum(FIELD_WEIGHTS[k] * per_field[k] for k in FIELD_WEIGHTS)

    subtotal, tax, total = (_dec(fields.get(k)) for k in ("subtotal", "tax_amount", "total_amount"))
    if subtotal is not None and tax is not None and total is not None:
        if abs(subtotal + tax - total) > Decimal("0.02"):
            overall -= 0.20
            for key in ("subtotal", "tax_amount", "total_amount"):
                per_field[key] = min(per_field[key], 0.3)
            reasons.append("subtotal + tax does not equal the total")

    invoice_date, due_date = fields.get("invoice_date"), fields.get("due_date")
    if isinstance(invoice_date, date) and isinstance(due_date, date) and due_date < invoice_date:
        overall -= 0.10
        per_field["invoice_date"] = min(per_field["invoice_date"], 0.4)
        per_field["due_date"] = min(per_field["due_date"], 0.4)
        reasons.append("due date is before the invoice date")

    if validation_errors:
        overall -= min(0.30, 0.05 * len(validation_errors))
        reasons.append(f"{len(validation_errors)} validation issue(s) reported")

    if model_confidence is not None:
        try:
            model_value = max(0.0, min(1.0, float(model_confidence)))
            overall = 0.6 * overall + 0.4 * model_value
        except (TypeError, ValueError):
            pass

    overall = round(max(0.0, min(1.0, overall)), 3)
    per_field = {k: round(v, 3) for k, v in per_field.items()}
    return overall, per_field, reasons
