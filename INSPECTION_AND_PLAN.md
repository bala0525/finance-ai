# Azentmart Finance AI – Inspection Report & Plan (this pass)

## Verified by reading the code
- Stack: FastAPI + SQLAlchemy + Alembic (single head i9j0k1l2m3n4), React frontend, Supabase Storage, Stripe (AR only).
- Role routing at upload, approve, reject, request-changes and pay exists in `routes/documents.py`.
  - Employee upload -> Finance User/Manager approve -> PENDING_PAYMENT.
  - Finance User upload -> another FU/FM -> PENDING_CA_APPROVAL -> CA approves -> payer reset to the original uploader.
  - Finance Manager upload -> CA -> PENDING_PAYMENT (payer = manager-selected FU).
  - Chief Accountant upload -> assigned FU directly (no approval).
- Self-approve / self-reject blocked in the backend. Payment is Finance User only, amount must match, ledger posting is voucher-idempotent.
- "Verify GST" link to the exact portal URL exists in EmployeeWorkspace.js and WorkflowPanelsA.js (link only; no automatic verification).

## Gaps found (not yet fixed)
1. No side-by-side invoice detail workspace (document preview + editable fields + approval history + payment/ledger).
2. Duplicate detection is per uploader (`find_duplicate_invoice(owner_id)`), so the same invoice uploaded by two users is not flagged.
3. Missing extracted fields: GSTIN/CGST/SGST/IGST, line items, PO, buyer, bank details (the Document model stores only 7 fields).
4. AP payment is manual bank transfer with a reference; there is no AP gateway. Stripe covers AR collections only.
5. `/agents` workspace data: live-data verification of all 8 agents was not completed in this pass.
6. Several `.bak` / `.before_*` / `.approval-backup` files are left in the tree.
7. Existing tests are mostly source-string checks; the DB-backed tests need `pgserver`, which was not available.

## Changed in this pass
- `POST /documents/{id}/reject`, `/request-changes`, `/pay` now take a row lock (`SELECT ... FOR UPDATE`), closing a concurrent double-action window.
- New `PATCH /documents/{id}/extracted-fields`: audited correction of vendor, invoice number, dates, subtotal, tax, total.
  - Allowed for the uploader or Finance User/Manager/Chief Accountant (pre-approval statuses only).
  - Locked once the invoice is pending payment, paid, rejected, or in Chief Accountant approval.
  - Re-runs validation and duplicate check; stores before/after in the audit log; keeps original values on the first edit.
  - No schema change, no migration.
- New `services/invoice_edit.py` and `tests/test_invoice_edit.py`.

## Verification status
- Python compile of `app` and `tests`: passed.
- `test_invoice_edit.py`: 6 passed, run through a small shim runner, because pytest is not installed here.
- NOT run: FastAPI app import, the endpoint itself, existing pytest suite (no fastapi/pytest/pgserver, network disabled), Alembic, frontend build, live DB/Stripe.
