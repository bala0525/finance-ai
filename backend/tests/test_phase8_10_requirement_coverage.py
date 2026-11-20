"""Regression checks for Phase 8-10 workflow requirements."""
from pathlib import Path


def test_all_eight_existing_agents_remain_registered():
    # Registry verification is static and should not require database drivers/config.
    source = (Path(__file__).resolve().parents[1] / "app/routes/agents.py").read_text()
    expected = {
        "accounts-payable", "accounts-receivable", "invoice-processing", "reconciliation",
        "finance-analyst", "expense", "financial-reporting", "fraud-detection",
    }
    registered = {slug for slug in expected if f'"slug": "{slug}"' in source or f'"{slug}"' in source}
    assert registered == expected
    import re
    assert len(re.findall(r"\"slug\"\s*:\s*\"[a-z-]+\"", source)) == 8


def test_gateway_status_and_checkout_are_finance_user_only():
    source = (Path(__file__).resolve().parents[1] / "app/routes/ar_sales.py").read_text()
    assert 'def stripe_gateway_status(user: User = Depends(require_roles("Finance User")))' in source
    assert 'def create_stripe_checkout(invoice_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles("Finance User")))' in source


def test_finance_user_upload_has_chief_accountant_handoff():
    source = (Path(__file__).resolve().parents[1] / "app/routes/documents.py").read_text()
    assert 'uploader_role in {"Finance Manager", "Finance User"} and role == "Chief Accountant" and previous_status == "PENDING_CA_APPROVAL"' in source
    assert 'document.assigned_finance_user_id = document.owner_id' in source


def test_ledger_posting_helpers_keep_document_source_links_for_ap_and_expense():
    source = (Path(__file__).resolve().parents[1] / "app/services/posting.py").read_text()
    assert 'source_document_id=document_id' in source
    assert 'source_type="AR_INVOICE", source_id=f"AR-SALES-INVOICE-{invoice_id}"' in source
    assert 'source_type="AR_COLLECTION"' in source
    assert 'source_type="EXPENSE_REIMBURSEMENT"' in source


def test_sales_invoice_rejection_and_stripe_payment_audit_fields_exist():
    model = (Path(__file__).resolve().parents[1] / "app/models/sales_invoice.py").read_text()
    route = (Path(__file__).resolve().parents[1] / "app/routes/ar_sales.py").read_text()
    assert "rejected_by" in model and "rejected_at" in model
    assert "payer_email" in model
    assert "paid_by_customer_email" in route and "Stripe webhook" in route
