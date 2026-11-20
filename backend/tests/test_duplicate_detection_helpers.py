from pathlib import Path

from app.services.duplicate_detection import (
    normalize_invoice_number,
    normalize_vendor_identity,
    sha256_document,
)


def test_invoice_number_normalization_catches_formatting():
    assert normalize_invoice_number(" INV-2026 / 001 ") == "inv2026001"
    assert normalize_invoice_number("inv 2026.001") == "inv2026001"


def test_invoice_number_missing_is_empty():
    assert normalize_invoice_number(None) == ""
    assert normalize_invoice_number("   ") == ""


def test_vendor_normalization_catches_punctuation_and_spacing():
    assert normalize_vendor_identity("ABC Pvt. Ltd.") == "abcpvtltd"
    assert normalize_vendor_identity("abc pvt ltd") == "abcpvtltd"


def test_vendor_missing_is_empty():
    assert normalize_vendor_identity(None) == ""


def test_sha256_same_content_same_hash_regardless_filename():
    content = b"invoice sample bytes"
    assert sha256_document(content) == sha256_document(content)
    assert len(sha256_document(content)) == 64


def test_sha256_changes_with_content():
    assert sha256_document(b"file one") != sha256_document(b"file two")


def test_duplicate_is_rechecked_at_approval_and_payment():
    source = (Path(__file__).resolve().parents[1] / "app/routes/documents.py").read_text()
    approve = source[source.index("def approve_invoice("):source.index("def reject_invoice(")]
    pay = source[source.index("def pay_invoice("):source.index("MEDIA_TYPES =")]
    assert "find_duplicate_invoice(db, document, document.owner_id)" in approve
    assert "Duplicate invoice detected. Approval is blocked." in approve
    assert "find_duplicate_invoice(db, document, document.owner_id)" in pay
    assert "DUPLICATE_PAYMENT_BLOCKED" in pay


def test_duplicate_original_details_are_tenant_and_permission_scoped():
    source = (Path(__file__).resolve().parents[1] / "app/routes/documents.py").read_text()
    assert "match.owner.tenant_id != current_user.tenant_id" in source
    assert "if not can_access_document(current_user, match):" in source
    assert '"duplicateMatch"' in source
