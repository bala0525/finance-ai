# Implementation Progress — Remaining Tasks from v3

## Current checkpoint (2026-11-19)

| Workstream | Status | Changes in this checkpoint | Verification | Remaining |
|---|---|---|---|---|
| Phase A — audit refresh | PARTIAL | Re-inspected v3 reports, duplicate migration, models, upload/extraction/approval/payment routes, frontend workspace, tests | Static inspection | Runtime/live DB audit |
| Phase B — duplicate detection | PARTIAL, improved | Tenant-scoped exact SHA-256 + normalized invoice number/vendor matching; ORM fields for existing FIN-05 migration; original-match API details; duplicate recheck before approval and payment; hash backfill script; frontend match warning | 8 helper/source tests passed; syntax compilation passed | Migration/live DB validation; hash backfill run; concurrency tests; GSTIN-based matching unavailable in current extraction schema; tenant/company semantics review |
| Phase C — invoice model | PARTIAL | Added JSONB `extracted_invoice_details` and `line_items`; expanded extraction prompt/response; new Alembic migration | Syntax compilation; migration history shows single head | Migration not applied; UI editing/display for extended fields; validation of line-item financials; safe extraction accuracy tests |
| Phase D — invoice workspace | PARTIAL/UNVERIFIED | Duplicate-match details now surfaced in existing invoice workspace rows | Static inspection | Full split preview/detail workspace, field edit UI for expanded fields, histories, payment/ledger panel |
| Phase E — workflow | UNVERIFIED | Added approval-time duplicate revalidation | Source-level regression tests | End-to-end workflow and negative-role tests |
| Phase F — payment/ledger | UNVERIFIED | Added payment-time duplicate revalidation and audit event for blocked duplicate | Static tests | DB/payment concurrency, failure/retry, ledger integration tests |
| Phase G — AI Employees | UNVERIFIED | Registry regression test changed to static check to avoid DB driver requirement | 8-agent registry source test included in 19 targeted tests | Live DB/data-source/calc tests for each agent |
| Phase H — documents | UNVERIFIED | Existing code reviewed | Existing storage tests cannot run due missing `pgserver` | Runtime preview/download/delete/Supabase tests |
| Phase I — RBAC/UI | PARTIAL | Duplicate warning displays original details only when API permission checks allow | Static review | Full permission matrix and UI regression |
| Phase J — regression/security | PARTIAL | Test subsets run; compilation and Alembic history checked | 54 tests passed excluding storage suite; full suite 56 passed / 20 errors | Storage suite requires `pgserver`; DB migration/live tests and frontend build unavailable |

## Files changed this checkpoint

- `backend/app/services/duplicate_detection.py` — pure normalization and SHA-256 helpers
- `backend/app/routes/documents.py` — hash storage on upload; hash/business duplicate match; duplicate metadata; recheck on approval/payment/edit; permission-scoped original match details
- `backend/app/models/document.py` — ORM mappings for FIN-05 duplicate columns and extended invoice JSON fields
- `backend/app/services/invoice_extractor.py` — extraction prompt/response for additional invoice details and line items; no missing values are filled by code
- `backend/app/services/__init__.py` — lazy `AuthService` export so pure service imports do not load password dependencies unnecessarily
- `backend/scripts/backfill_duplicate_hashes.py` — safe per-document Supabase hash backfill script
- `backend/alembic/versions/j1k2l3m4n5o6_expand_invoice_extraction_json.py` — safe nullable JSONB migration
- `backend/tests/test_duplicate_detection_helpers.py` — focused duplicate helper and guard regression tests
- `backend/tests/test_phase8_10_requirement_coverage.py` — agent registry test made static/environment-independent
- `Frontend/src/pages/Employees/EmployeeWorkspace.js` — duplicate warning shows matching original invoice details when authorized


## Database changes

- Existing FIN-05 migration `a9d4f6b2c801` already adds duplicate hash/match columns and an index; this checkpoint mapped those existing columns into SQLAlchemy.
- New migration `j1k2l3m4n5o6` adds nullable `extracted_invoice_details` and `line_items` JSONB columns.
- Alembic reports one head: `j1k2l3m4n5o6`.
- Neither migration was applied to a live database in this environment.

## Tests

- Targeted duplicate/edit/phase requirement tests: **19 passed**.
- Backend tests excluding `test_storage_flow.py`: **54 passed**.
- Full backend suite: **56 passed, 20 errors**. All 20 errors occur in `test_storage_flow.py` setup because `pgserver` is not installed.
- Python syntax compilation: passed for changed backend modules and tests.
- Frontend build: not run; `Frontend/node_modules` is absent and network is unavailable for dependency installation.
- Live database/Supabase/Gemini tests: not run.

## Blockers / risks

- The environment cannot install missing dependencies because internet/DNS is unavailable.
- `pgserver` missing blocks storage-flow integration tests.
- PostgreSQL drivers missing block route imports/live DB tests.
- No project `.env` or real Supabase/Gemini credentials were used.
- Duplicate business matching currently uses normalized invoice number plus vendor name where both are present; GSTIN-based matching is not implemented because the current extraction/model does not yet persist GSTIN as a typed field.
- Exact file hashes for existing documents must be backfilled before exact-file duplicate detection covers historical records.
- Extended invoice JSON fields are stored, but the full invoice detail workspace and edit UI remain incomplete.

## Next task

1. Apply migration in a safe staging/backup database and verify ORM/schema consistency.
2. Run `python -m app.scripts.backfill_duplicate_hashes` with real configured storage/database.
3. Add DB-backed cross-user duplicate tests and concurrent upload/payment tests.
4. Complete the invoice detail workspace and editing UI for extended fields/line items.
5. Continue remaining workflow/payment/AI/document/security regression tasks.
