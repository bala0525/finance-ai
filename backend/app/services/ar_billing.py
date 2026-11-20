"""Pure AR billing calculations and Stripe webhook signature verification."""
import hashlib
import hmac
import time
from decimal import Decimal, ROUND_HALF_UP

CENT = Decimal("0.01")


def money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def calculate_invoice_totals(lines, gst_rate: Decimal):
    if not lines:
        raise ValueError("At least one invoice line is required")
    subtotal = Decimal("0.00")
    line_totals = []
    for line in lines:
        quantity = Decimal(str(line.quantity))
        unit_price = Decimal(str(line.unit_price))
        if quantity <= 0 or unit_price < 0:
            raise ValueError("Quantity must be positive and unit price cannot be negative")
        line_total = money(quantity * unit_price)
        subtotal += line_total
        line_totals.append(line_total)
    subtotal = money(subtotal)
    gst_amount = money(subtotal * Decimal(str(gst_rate)) / Decimal("100"))
    return line_totals, subtotal, gst_amount, money(subtotal + gst_amount)


def stripe_signature_valid(payload: bytes, header: str, secret: str, tolerance: int = 300, now: int | None = None) -> bool:
    try:
        parts = {}
        for item in header.split(","):
            key, value = item.split("=", 1)
            parts.setdefault(key, []).append(value)
        timestamp = int(parts["t"][0])
        current = int(time.time()) if now is None else int(now)
        if abs(current - timestamp) > tolerance:
            return False
        signed = str(timestamp).encode() + b"." + payload
        expected = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
        return any(hmac.compare_digest(expected, signature) for signature in parts.get("v1", []))
    except (KeyError, ValueError, IndexError):
        return False
