from decimal import Decimal
import hashlib
import hmac
import time

import pytest

from app.services.accounting import validate_balanced_journal, normal_balance, account_balance
from app.services.ar_billing import calculate_invoice_totals, stripe_signature_valid


class Line:
    def __init__(self, quantity, unit_price):
        self.quantity = quantity
        self.unit_price = unit_price


def test_invoice_gst_rounding():
    lines, subtotal, gst, total = calculate_invoice_totals(
        [Line("2", "100.00"), Line("1", "50.00")], Decimal("18")
    )
    assert lines == [Decimal("200.00"), Decimal("50.00")]
    assert subtotal == Decimal("250.00")
    assert gst == Decimal("45.00")
    assert total == Decimal("295.00")


def test_balanced_journal_accepts_multiple_lines():
    debit, credit = validate_balanced_journal([
        {"debit": "118.00", "credit": "0"},
        {"debit": "0", "credit": "100.00"},
        {"debit": "0", "credit": "18.00"},
    ])
    assert debit == credit == Decimal("118.00")


@pytest.mark.parametrize("lines", [
    [{"debit": "100", "credit": "0"}],
    [{"debit": "100", "credit": "0"}, {"debit": "0", "credit": "90"}],
    [{"debit": "100", "credit": "1"}, {"debit": "0", "credit": "101"}],
    [{"debit": "-1", "credit": "0"}, {"debit": "0", "credit": "-1"}],
])
def test_invalid_journals_rejected(lines):
    with pytest.raises(ValueError):
        validate_balanced_journal(lines)


def test_normal_balance_and_balance_math():
    assert normal_balance("ASSET") == "DEBIT"
    assert normal_balance("EXPENSE") == "DEBIT"
    assert normal_balance("LIABILITY") == "CREDIT"
    assert account_balance("ASSET", Decimal("120"), Decimal("20")) == Decimal("100")
    assert account_balance("LIABILITY", Decimal("20"), Decimal("120")) == Decimal("100")


def test_stripe_webhook_signature():
    payload = b'{"id":"evt_test","type":"checkout.session.completed"}'
    timestamp = int(time.time())
    secret = "whsec_test"
    digest = hmac.new(secret.encode(), str(timestamp).encode() + b"." + payload, hashlib.sha256).hexdigest()
    assert stripe_signature_valid(payload, f"t={timestamp},v1={digest}", secret)
    assert not stripe_signature_valid(payload, f"t={timestamp},v1=bad", secret)
