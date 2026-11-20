# Azentmart Finance AI — Completion Plan

## Confirmed business decisions
- AR customer collections: Stripe Checkout with verified webhooks.
- AP supplier payments: manual bank transfer; capture transfer reference, date, proof, confirmer and accounting posting. No automatic payout API.
- Preserve the existing eight AI Employee workspaces and dark navy/cyan UI.
- Preserve AP business sequence: Finance User upload → Finance Manager approval → Chief Accountant final approval → Invoice Processing for the original uploader → Finance User payment batch → Chief Accountant batch approval → Finance User records confirmed manual transfer → General Ledger.
- AR sequence: Finance User drafts customer sales invoice → Finance Manager approval → Administrator final approval → final invoice number/PDF → send to customer → Stripe payment → verified webhook → collection journal.
- Roles: Employee / Requester, Finance User, Finance Manager, Chief Accountant, Administrator. Public signup remains Employee / Requester only.

## Delivery stages and acceptance criteria

### Stage 0 — Baseline and safety
- Inventory source, dependencies, migrations, APIs, role rules and existing tests.
- Keep original ZIP untouched; work on an extracted copy.
- Never copy `.env`, secrets, virtual environments, `node_modules`, build output or macOS metadata into the delivery ZIP.
- Record known gaps and baseline test outcomes.

### Stage 1 — Identity, tenant isolation and workflow policy
- Enforce tenant-scoped access in every finance query and API.
- Add explicit workflow states and immutable approval events.
- Prevent self-approval and enforce role-specific transition rules.
- Acceptance: negative API tests prove cross-tenant reads/writes and unauthorized transitions return 403/404.

### Stage 2 — Accounts Payable
- Keep current duplicate, extraction, validation, exceptions and batch controls.
- Implement Finance Manager → Chief Accountant invoice approval.
- Ensure approved invoice enters Invoice Processing for its original Finance User only.
- Add manual supplier payment evidence, transfer reference, paid-by/paid-at audit and idempotent AP journal posting after batch approval.
- Acceptance: AP regression tests; no payment can be recorded before batch approval; duplicate payment posting is blocked.

### Stage 3 — Accounts Receivable
- Customer master, invoice draft, line items, GST, totals, validation and invoice numbering.
- Finance Manager first approval; Administrator final approval.
- Generate final invoice PDF only after final approval; email delivery with retry/status tracking.
- Acceptance: totals calculated server-side; invoice number unique per tenant; draft cannot be paid.

### Stage 4 — Stripe collections
- Stripe Checkout Session creation for approved AR invoices.
- Store provider/session/payment IDs and idempotency key.
- Verify Stripe webhook signatures; process events idempotently; handle success, failure, expiry, refunds and partial-payment policy.
- Post collection journals only after verified payment events.
- Acceptance: Stripe test-mode integration tests and invalid-signature/replayed-event tests.

### Stage 5 — General Ledger and close
- Complete tenant-scoped Chart of Accounts, journals, posting rules, reversals and audit.
- Verify double-entry and account-code integrity at database/service boundaries.
- Trial Balance, General Ledger, P&L, Balance Sheet, Cash Flow, period locks and close checklist.
- Acceptance: accounting fixture tests prove debit=credit and statement tie-outs.

### Stage 6 — Banking and reconciliation
- Bank statement CSV/XLSX import, normalization, duplicate detection, matching suggestions, manual match/unmatch, exceptions and adjustment journals.
- Month-close revalidation against latest source data.
- Acceptance: golden reconciliation datasets and idempotent imports.

### Stage 7 — Eight AI workspaces and operational workflows
- Verify each workspace uses live tenant-scoped database data, not mock data.
- Complete expense reimbursement approvals, invoice processing, finance analyst, reporting and fraud review actions.
- Notifications, scheduler/retries, audit and task ownership.
- Acceptance: role-by-role end-to-end workflow tests.

### Stage 8 — Documents, reports and production readiness
- Preview/download, recoverable trash, storage cleanup, PDF/XLSX reports, exports and drill-down.
- Security review, migrations on a disposable DB, frontend build, backend tests, setup guide and deployment checklist.
- Acceptance: all tests pass; no secrets or runtime folders in final ZIP.

## External prerequisites
- Stripe test secret key and webhook signing secret are required for live test-mode checkout/webhook verification. Keep these in local environment variables only.
- SMTP/provider credentials are required for real outbound email.
- A test PostgreSQL/Supabase project is required to execute migrations and database integration tests.
- Manual AP payments do not require bank API credentials, but a human must confirm transfer evidence.

## Current baseline from supplied ZIP
- React 18 / CRA frontend; FastAPI backend; SQLAlchemy and Alembic.
- Existing migrations now form one linear head at `f3c9a7d2b5e1` after the two added workflow/auth migrations.
- Existing ledger tables and posting helpers exist; existing AR routes are collection/reminder/dispute oriented.
- Stripe Checkout and signed webhook foundations were added in the prior implementation pass; refunds and provider reconciliation remain outstanding.
- The actual AP invoice approval path is Finance Manager → Chief Accountant; it has been preserved.
- Existing backend source parses successfully (55 Python files). Runtime test collection is currently blocked in this environment because `pwdlib` is not installed; frontend build is blocked because `node_modules` is excluded from the source extraction.

## Progress update — implementation pass 1
- Completed initial inventory and added the implementation plan/audit documents.
- Confirmed actual AP invoice approval already follows Finance Manager → Chief Accountant; kept that logic unchanged.
- Tightened tenant scoping for document/workspace/payment-batch access and restricted Finance User Invoice Processing visibility to own uploads.
- Added AR sales invoice draft, submit, Manager approval, Administrator final approval, rejection, PDF download, SMTP email and Stripe Checkout/webhook foundations.
- Added AP manual transfer reference/date/bank/proof-reference capture before mark-paid and preserved Chief Accountant batch approval.
- Added AR arithmetic/signature unit tests; 4/4 pass.
- Remaining stages are still required before calling the application complete; see `IMPLEMENTATION_STATUS.md` and `IMPLEMENTATION_AUDIT.md`.
- Added AR PDF generation, SMTP send status, invoice audit history and setup instructions. GST place-of-supply/tax document compliance and durable email retries remain outstanding.


## Progress update — implementation pass 2
- Fixed public signup tenant assignment and role landing after login.
- Added password reset API + SMTP email delivery and a reset-password screen.
- Added Finance User expense verification before Finance Manager and Administrator decisions, with tenant-scoped access and audit timestamps.
- Added explicit Expense Employee upload routing.
- Added migrations `f2b8d4a6c1e9` and `f3c9a7d2b5e1`.
- This remains an implementation-in-progress snapshot; outstanding work is listed in `IMPLEMENTATION_STATUS.md`.
