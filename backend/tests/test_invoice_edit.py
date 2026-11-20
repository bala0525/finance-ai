"""Pure unit tests for services/invoice_edit.py (no DB / FastAPI needed)."""
import importlib.util
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location(
    "invoice_edit", Path(__file__).resolve().parents[1] / "app" / "services" / "invoice_edit.py"
)
ie = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ie)


def test_rejects_unknown_and_empty():
    with pytest.raises(ie.FieldEditError):
        ie.normalise_edits({"status": "PAID"})
    with pytest.raises(ie.FieldEditError):
        ie.normalise_edits({})


def test_cannot_edit_approval_or_payment_fields():
    for key in ("status", "approved_by", "paid_at", "payment_amount", "assigned_finance_user_id", "owner_id"):
        with pytest.raises(ie.FieldEditError):
            ie.normalise_edits({key: 1})


def test_coercion_and_bad_values():
    out = ie.normalise_edits({"total_amount": "1180.5", "invoice_date": "2026-11-01", "vendor_name": "  Acme "})
    assert out == {"total_amount": Decimal("1180.50"), "invoice_date": date(2026, 11, 1), "vendor_name": "Acme"}
    for bad in ({"total_amount": "abc"}, {"total_amount": "-1"}, {"total_amount": "NaN"}, {"invoice_date": "01/11/2026"}):
        with pytest.raises(ie.FieldEditError):
            ie.normalise_edits(bad)


def test_validation_total_mismatch_and_dates():
    f = {"vendor_name": "A", "invoice_number": "1", "invoice_date": date(2026, 11, 5), "due_date": date(2026, 11, 1),
         "subtotal": Decimal("1000"), "tax_amount": Decimal("180"), "total_amount": Decimal("1200")}
    errs = ie.validate_fields(f)
    assert "Subtotal plus tax does not match the invoice total." in errs
    assert "Due date is earlier than invoice date." in errs
    f.update(total_amount=Decimal("1180"), due_date=date(2026, 12, 1))
    assert ie.validate_fields(f) == []


def test_missing_required():
    assert len(ie.validate_fields({})) == 4


def test_diff_only_changed():
    d = ie.diff_fields({"total_amount": Decimal("10"), "vendor_name": "A"}, {"total_amount": Decimal("10.00"), "vendor_name": "B"})
    assert d == {"vendor_name": {"from": "A", "to": "B"}}
