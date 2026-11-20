import hashlib
import hmac
from decimal import Decimal

import pytest

from app.services.ar_billing import calculate_invoice_totals, money, stripe_signature_valid


class Line:
    def __init__(self, quantity, unit_price):
        self.quantity = Decimal(str(quantity))
        self.unit_price = Decimal(str(unit_price))


def test_invoice_totals_are_server_calculated_and_rounded():
    lines, subtotal, gst, total = calculate_invoice_totals([Line("2", "125.50"), Line("1.5", "10")], Decimal("18"))
    assert lines == [Decimal("251.00"), Decimal("15.00")]
    assert subtotal == Decimal("266.00")
    assert gst == Decimal("47.88")
    assert total == Decimal("313.88")


def test_invoice_totals_reject_invalid_quantity():
    with pytest.raises(ValueError):
        calculate_invoice_totals([Line("0", "10")], Decimal("18"))


def test_stripe_signature_accepts_valid_and_rejects_tampered_or_stale():
    secret = "whsec_test_secret"
    payload = b'{"id":"evt_test","type":"checkout.session.completed"}'
    timestamp = 1_800_000_000
    signed = str(timestamp).encode() + b"." + payload
    digest = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
    header = f"t={timestamp},v1={digest}"
    assert stripe_signature_valid(payload, header, secret, now=timestamp)
    assert not stripe_signature_valid(payload + b" ", header, secret, now=timestamp)
    assert not stripe_signature_valid(payload, header, secret, now=timestamp + 600)
    assert not stripe_signature_valid(payload, "bad-header", secret, now=timestamp)


def test_money_rounding():
    assert money(Decimal("1.005")) == Decimal("1.01")


def test_sales_invoice_pdf_is_generated_for_final_invoice():
    from datetime import date
    from types import SimpleNamespace
    from app.services.invoice_pdf import render_sales_invoice_pdf

    invoice = SimpleNamespace(
        invoice_number="AR-1-00000001", status="APPROVED", customer_name="Acme Ltd",
        customer_email="accounts@example.com", customer_gstin=None,
        invoice_date=date(2026, 11, 1), due_date=date(2026, 11, 30), gst_rate=Decimal("18"),
        subtotal=Decimal("100.00"), gst_amount=Decimal("18.00"), total_amount=Decimal("118.00"),
        amount_paid=Decimal("0.00"),
        lines=[SimpleNamespace(description="Consulting service", quantity=Decimal("1"), unit_price=Decimal("100.00"), line_total=Decimal("100.00"))],
    )
    pdf = render_sales_invoice_pdf(invoice)
    assert pdf.startswith(b"%PDF") and len(pdf) > 500
