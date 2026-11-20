# Initial implementation audit

| Area | Supplied code evidence | Status |
|---|---|---|
| Authentication / five roles | JWT/auth routes, role model, role seeder, role guards | Partial; end-to-end authorization needs tests |
| Eight workspaces | React workspace routes and FastAPI agent/workflow routes | Present; live-data and permissions need per-workspace verification |
| AP extraction / duplicate / exceptions | Document routes and AP workflow service | Present |
| AP invoice approval | Existing policy is Finance Manager + Administrator | Does not match required Finance Manager + Chief Accountant |
| AP payment batch | Chief Accountant approval and Finance User mark-paid gate exist | Partial; transfer reference/date/bank/proof-reference now recorded; actual proof upload still pending |
| AR collection/reminders/disputes | Existing routes and posting helper | Present but not a sales-invoice lifecycle |
| AR invoice creation/approval/PDF/email | Sales invoice model, draft/submit/Manager/Admin approval APIs added in this pass | Partial; PDF/email still missing |
| Stripe customer payments | No Stripe dependency, Checkout API or webhook route found | Missing |
| General Ledger | LedgerAccount, JournalLine, PartyInvoice, posting helpers and statement service | Partial; close/reversal/controls need verification |
| Banking integration | Reconciliation/import foundations | Partial; live bank feed not found |
| Tenant isolation | Tenant migration and User.tenant_id exist; document/agent/workflow/AP batch query scoping tightened in this pass | Partial; complete API-by-API regression audit still required |
| Documents | Supabase storage and protected delete | Partial; soft delete/trash missing |
| Tests | Two backend test modules present | Insufficient; collection blocked here by missing pwdlib |

## Safety notes
- The uploaded ZIP includes a backend `.env`. It has been intentionally excluded from the working copy and will not be included in the final ZIP. Rotate any credentials that were shared in that archive if they are real.
- Original uploaded ZIP remains unchanged.
- No database migrations have been run against the user's Supabase project.


## Updates from implementation pass

- AP Manager → Chief Accountant approval path was already present in the actual `documents.py` implementation; the handoff status document was stale on this point. The batch approval path was also already Chief Accountant-gated.
- Fixed a critical visibility issue in shared document/workspace queries: tenant boundaries are now applied, and Finance Users only see their own uploaded documents in Invoice Processing.
- Added initial AR sales invoice and Stripe payment lifecycle endpoints and manual AP transfer evidence capture. These are not yet a claim of full production completion.
- Added an Accounts Receivable invoice draft form and status/action table to the existing AR workspace; the frontend invokes the new AR invoice and Stripe APIs.
- AR final-approved invoices can now be rendered as PDFs and emailed through configured SMTP; delivery status is stored on the invoice. SMTP credentials remain external configuration.
- Stripe webhook now handles checkout expiry and async payment failure/success events in addition to paid checkout completion.


## Pass 2 addendum
- Public signup now assigns the existing default tenant and Employee / Requester role; signup previously omitted the required `tenant_id`.
- Forgot-password UI now calls a one-time, hashed, expiring password-reset token API and sends via configured SMTP.
- Login now lands through role-based routing rather than hard-coded AP.
- Expense submission now has Finance User verification → Finance Manager review → Administrator final decision → Finance User reimbursement.
- Remaining limitations and environment test blockers are recorded in `IMPLEMENTATION_STATUS.md`.

## Phase 1–5 follow-up addendum (2026-11-13)

The latest source update supersedes earlier “still missing” notes for email verification, linked expense resubmission, notification inbox and AP proof upload. See `PHASE_1_TO_5_REPORT.md` for exact implementation details. AP invoice approvals remain Finance Manager → Chief Accountant; AP batch approval remains Chief Accountant; AR invoice approval remains Finance Manager → Administrator. Admin is monitoring-only for AP invoice approval, and Chief Accountant is monitoring-only for AR invoice approval.

The source has passed static Python and frontend JS/JSX syntax checks and has a single Alembic head (`f4a1b8c2d6e0`). Full pytest, React production build, live DB migration, Supabase Storage and SMTP checks have not passed/been executed in this environment due unavailable runtime packages and external credentials.
