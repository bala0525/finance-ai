# Project Audit — Updated from v3 (2026-11-19)

Statuses are evidence-based and distinguish source inspection from runtime verification.

| Requirement | Existing/current implementation | Status | Files | Remaining action |
|---|---|---|---|---|
| Approval workflows | Role-routed document approval logic exists | PARTIAL / UNVERIFIED | `backend/app/routes/documents.py` | DB-backed end-to-end workflow tests |
| Upload/storage | Supabase storage upload/download code exists | UNVERIFIED | routes/storage service | Storage integration tests require pgserver/Supabase |
| Invoice extraction | Base vendor/invoice/date/tax/total extraction; prompt now requests extended details and line items | PARTIAL | `invoice_extractor.py`, `documents.py` | Accuracy tests and UI integration |
| Invoice editing | Audited correction endpoint for limited core fields | PARTIAL | `invoice_edit.py`, `documents.py` | Extended fields and line items edit UI/API |
| Global duplicate detection | Tenant-scoped hash + normalized invoice identity/vendor; hash columns mapped; approval/payment revalidation added | PARTIAL | duplicate service, documents routes/model | Historical backfill, DB concurrency tests, GSTIN matching, review false positives |
| Payment processing | Manual AP payment and AR Stripe flow exist | PARTIAL / UNVERIFIED | AP/AR routes, posting service | Runtime failure/retry/ledger tests |
| Ledger posting | Existing AP/expense/AR posting helpers and idempotency logic | PARTIAL / UNVERIFIED | `services/posting.py` | Live DB transaction tests |
| GST | Manual GST portal link exists | PARTIAL | frontend | Verify links; automated API/GSP access is external/blocker |
| AP payment gateway | No verified real AP gateway | MISSING/BLOCKED | AP routes/config | Provider/merchant credentials and integration |
| AI Employees | 8 registry entries and workspace/API code exist | UNVERIFIED | agents route/frontend | Live DB source/calc/auth tests per agent |
| Database migrations | Existing chain plus new invoice JSON migration; one Alembic head | UNVERIFIED | backend/alembic | Apply/rollback on staging and schema verification |
| Frontend integration | Existing React workspaces and APIs; duplicate detail warning added | PARTIAL | `EmployeeWorkspace.js` | Build/browser tests; full invoice detail workspace |
| Preview/download | Storage-backed APIs exist | UNVERIFIED | routes/storage service | Integration tests for all formats |
| Safe delete | Existing storage delete code and tests | UNVERIFIED | documents routes/storage | Integration/authorization tests |
| RBAC | Backend role dependencies/workflow checks exist | PARTIAL | dependencies/routes | Negative tests across full permission matrix |
| Audit logs | Document audit event model/workflow events exist; duplicate-payment block event added | PARTIAL | audit model/routes | Sensitive-action audit coverage verification |
| Tests | Existing suite plus focused duplicate tests | PARTIAL | backend/tests | Storage suite blocked by missing pgserver; live DB/frontend regression |
