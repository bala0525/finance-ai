# Phase 8–10 Gap Fix Report (B2, B5, B7, E1, E2, E3)

## Changes in this update

- **B2:** AP payment posting retains `JournalLine.source_document_id` for the source invoice document. The source file remains in Supabase Storage and the ledger lines reference its document row; no duplicate physical file is created.
- **B5:** Chief Accountant approval now accepts both Finance Manager and Finance User uploads at `PENDING_CA_APPROVAL`. Finance User uploads are reassigned to the original uploader as payer at this stage and receive a payment assignment notification. Existing assigned-payer checks remain in the final-payment endpoint.
- **B7:** Existing Stripe gateway status endpoint is backend-protected with `require_roles("Finance User")`; frontend setup panel is rendered only for Finance User. API keys remain environment-configured and are not exposed. This update does not add an in-UI secret/key editor.
- **E1:** Existing AP, expense reimbursement, AR invoice recognition, AR collection, and AR refund accounting helpers remain the transaction posting paths. AP and expense journal lines link directly to their stored source documents. AR ledger entries use source type and source IDs identifying the sales invoice/payment/refund. Posting helpers are voucher-idempotent.
- **E2:** Added regression checks that all eight existing agent slugs remain registered, and workflow compatibility checks for the touched routing/payment/ledger surfaces. No agent names/slugs were renamed.
- **E3:** AP/expense documents already carry uploader/reviewer/verifier/payer fields and audit events. Added Sales Invoice rejection actor/timestamp fields and Stripe payment payer-email snapshot, with webhook audit details recording customer payer identity, payment intent, event, and timestamp.

## Migration

`backend/alembic/versions/i9j0k1l2m3n4_sales_invoice_audit_enhancements.py`

Adds nullable `sales_invoices.rejected_by`, `sales_invoices.rejected_at`, and `stripe_payments.payer_email`. Existing payer emails are backfilled from existing invoice customer emails. No existing rows are deleted.

## Verification performed

- Python compilation: passed for changed files and full `backend/app` and `backend/tests` compileall.
- Alembic head check: single head `i9j0k1l2m3n4`.
- ZIP integrity: verified after packaging.
- Full pytest collection: blocked because the current runtime does not have dependency `pwdlib` installed (`ModuleNotFoundError`). Tests were not reported as passing.
- Frontend production build: not run; `Frontend/node_modules` is absent in the packaging runtime.
- Live database migration and real payment/webhook tests: not run.

## Remaining deployment verification

Before production: install backend requirements, run `alembic upgrade head` against a backup/staging database, run pytest, install frontend dependencies and build, then execute manual workflow tests including B5 and role-negative tests.
