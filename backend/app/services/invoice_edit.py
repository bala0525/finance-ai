"""Pure helpers for audited manual correction of extracted invoice fields.

No framework imports so the logic can be unit-tested without a database.
"""

from datetime import date
from decimal import Decimal, InvalidOperation

EDITABLE_FIELDS = (
    "vendor_name",
    "invoice_number",
    "invoice_date",
    "due_date",
    "subtotal",
    "tax_amount",
    "total_amount",
)
DATE_FIELDS = {"invoice_date", "due_date"}
MONEY_FIELDS = {"subtotal", "tax_amount", "total_amount"}
TEXT_LIMITS = {"vendor_name": 255, "invoice_number": 150}

# Statuses where a correction cannot silently bypass an approval/payment decision.
EDITABLE_STATUSES = {
    "NEEDS_REVIEW",
    "NEEDS_CHANGES",
    "PENDING_REVIEW",
    "READY_FOR_REVIEW",
    "PENDING_MANAGER_APPROVAL",
    "PENDING_FINANCE_USER_VERIFICATION",
}
REVIEWER_EDIT_ROLES = {"Finance User", "Finance Manager", "Chief Accountant"}
TOLERANCE = Decimal("0.01")


class FieldEditError(ValueError):
    pass


def normalise_edits(raw: dict) -> dict:
    """Validate and coerce incoming edits. Unknown keys are rejected."""
    if not raw:
        raise FieldEditError("No fields supplied.")
    unknown = set(raw) - set(EDITABLE_FIELDS)
    if unknown:
        raise FieldEditError(f"Fields not editable: {', '.join(sorted(unknown))}.")
    out: dict = {}
    for key, value in raw.items():
        if value is None or (isinstance(value, str) and not value.strip()):
            out[key] = None
        elif key in DATE_FIELDS:
            try:
                out[key] = value if isinstance(value, date) else date.fromisoformat(str(value).strip())
            except ValueError as exc:
                raise FieldEditError(f"{key} must be an ISO date (YYYY-MM-DD).") from exc
        elif key in MONEY_FIELDS:
            try:
                amount = Decimal(str(value).strip())
            except InvalidOperation as exc:
                raise FieldEditError(f"{key} must be a number.") from exc
            if not amount.is_finite() or amount < 0:
                raise FieldEditError(f"{key} must be zero or greater.")
            out[key] = amount.quantize(Decimal("0.01"))
        else:
            text = str(value).strip()
            if len(text) > TEXT_LIMITS[key]:
                raise FieldEditError(f"{key} is too long (max {TEXT_LIMITS[key]}).")
            out[key] = text
    return out


def validate_fields(fields: dict) -> list[str]:
    """Same rule set as the extractor's validate_invoice, for edited values."""
    errors: list[str] = []
    labels = {
        "vendor_name": "Vendor name",
        "invoice_number": "Invoice number",
        "invoice_date": "Invoice date",
        "total_amount": "Total amount",
    }
    for key, label in labels.items():
        if fields.get(key) in (None, ""):
            errors.append(f"{label} is missing or invalid.")
    sub, tax, total = fields.get("subtotal"), fields.get("tax_amount"), fields.get("total_amount")
    if sub is not None and tax is not None and total is not None:
        if abs((Decimal(str(sub)) + Decimal(str(tax))) - Decimal(str(total))) > TOLERANCE:
            errors.append("Subtotal plus tax does not match the invoice total.")
    inv, due = fields.get("invoice_date"), fields.get("due_date")
    if inv and due and due < inv:
        errors.append("Due date is earlier than invoice date.")
    return errors


def diff_fields(before: dict, after: dict) -> dict:
    """Return {field: {"from": old, "to": new}} as JSON-safe strings for the audit log."""
    def fmt(v):
        return None if v is None else str(v)

    def same(a, b):
        if isinstance(a, Decimal) or isinstance(b, Decimal):
            try:
                return a is not None and b is not None and Decimal(str(a)) == Decimal(str(b))
            except InvalidOperation:
                return False
        return a == b

    return {
        k: {"from": fmt(before.get(k)), "to": fmt(after.get(k))}
        for k in after
        if not (before.get(k) is None and after.get(k) is None) and not same(before.get(k), after.get(k))
    }
