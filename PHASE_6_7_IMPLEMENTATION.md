# Azentmart Finance AI — Phase 6 and Phase 7 Implementation

## Phase 6 — Accounts Receivable and Stripe

### Existing workflow retained
- Finance User creates customer sales invoice draft.
- Finance User submits it for approval.
- Finance Manager gives first approval.
- Administrator gives final approval and invoice number is generated.
- Approved invoice PDF and customer email remain available.
- Stripe Checkout remains the customer payment channel.

### Changes in this implementation
- Final Administrator approval now recognizes the sales invoice in the General Ledger:
  - Debit Accounts Receivable for invoice total.
  - Credit Sales Revenue for taxable/subtotal amount.
  - Credit GST Payable for GST amount.
- Starter Chart of Accounts is created for the invoice owner when required.
- Partial payment collection can continue after a partial payment.
- Every Stripe Checkout attempt gets a distinct idempotency key.
- Stripe webhook signature, invoice/tenant metadata, currency and amount checks are retained.
- Each confirmed Stripe collection receives a payment-specific journal voucher so multiple instalments do not collide.
- Administrator can request a Stripe refund from the AR invoice table.
- Refund requests are durably recorded before the Stripe API call and use a stable idempotency key.
- `refund.updated` webhook updates pending refund status and posts accounting once on success.
- A successful refund reduces the invoice's net collected balance and posts the reverse cash/receivable movement.
- Stripe refunds are restricted to Administrator in this implementation.

### AR API routes
- `POST /agents/accounts-receivable/sales-invoices`
- `GET /agents/accounts-receivable/sales-invoices`
- `POST /agents/accounts-receivable/sales-invoices/{id}/submit`
- `POST /agents/accounts-receivable/sales-invoices/{id}/manager-approve`
- `POST /agents/accounts-receivable/sales-invoices/{id}/admin-approve`
- `POST /agents/accounts-receivable/sales-invoices/{id}/stripe-checkout`
- `POST /agents/accounts-receivable/sales-invoices/{id}/stripe-refunds`
- `POST /payments/stripe/webhook`

### Environment
Configure in `backend/.env`:
- `STRIPE_SECRET_KEY` — use Stripe test-mode key during testing.
- `STRIPE_WEBHOOK_SECRET` — signing secret for the webhook endpoint.
- `STRIPE_CURRENCY=inr`
- `FRONTEND_URL`
- SMTP settings for invoice email delivery.

Stripe dashboard/webhook configuration must point to:
`POST https://<backend-host>/payments/stripe/webhook`

Subscribe at minimum to:
- `checkout.session.completed`
- `checkout.session.async_payment_succeeded`
- `checkout.session.async_payment_failed`
- `checkout.session.expired`
- `refund.updated`

## Phase 7 — General Ledger and Accounting

### Chart of Accounts
- Tenant-scoped account listing.
- Create account endpoint restricted to Chief Accountant and Administrator.
- Starter accounts: Cash and Bank, Accounts Receivable, Accounts Payable, GST Payable, Owner Equity, Sales Revenue and Operating Expenses.
- Normal debit/credit balance rules.
- Existing per-user account ownership is retained for posting compatibility; company views aggregate account codes.

### Journal controls
- Tenant-scoped journal listing.
- Manual journal posting restricted to Chief Accountant and Administrator.
- Minimum two lines, one-sided debit/credit per line, equal non-zero totals.
- Account code validation.
- Period lock validation before posting.
- Journal reversal creates a new opposite-entry voucher and preserves the original.
- AP, AR, and expense posting helpers now attach tenant/source metadata and respect closed periods.
- Approved AR invoices are recognized once.
- Stripe collections use a unique voucher per Stripe payment.

### Financial statements
- Trial Balance with debit/credit equality flag.
- Profit and Loss with income, expenses and net profit.
- Balance Sheet with assets, liabilities, equity and current earnings.
- Cash Flow with actual bank/cash ledger inflows, outflows and net movement.

### Period close
- Chief Accountant can close a date range.
- Close checks all vouchers in the period for balanced debit/credit totals.
- Close checks the Trial Balance through period end.
- Closed periods reject new AP, AR, expense and manual journal postings through the shared posting/ledger controls.
- Period close records are tenant-scoped and auditable.

### Ledger API routes
- `GET /ledger/accounts`
- `POST /ledger/accounts`
- `POST /ledger/accounts/seed-defaults`
- `GET /ledger/journals`
- `POST /ledger/journals`
- `POST /ledger/journals/{voucher_no}/reverse`
- `GET /ledger/trial-balance`
- `GET /ledger/profit-and-loss`
- `GET /ledger/balance-sheet`
- `GET /ledger/cash-flow`
- `GET /ledger/period-closes`
- `POST /ledger/period-closes`

### Data safety
- New migration: `g6h7i8j9k0l1_phase6_7_ar_stripe_gl.py`.
- Adds tenant/source metadata to existing ledger rows without deleting historical rows.
- Adds accounting period close and Stripe refund tables.
- Ledger workbook import is now append-only; it no longer deletes the user's existing accounts and journal lines.
- Do not reset the database. Back up before applying migrations.

## Verification performed in this environment
- Python source syntax compilation: 118 Python files, zero syntax errors.
- Frontend JS/JSX transpile parse: 76 JavaScript files, zero syntax diagnostics.
- Alembic graph: one head, `g6h7i8j9k0l1`.
- Pure accounting/AR billing checks: 4 scenarios passed (GST arithmetic, balanced multi-line journal, invalid journal rejection, Stripe signature).
- Full pytest not run: environment is missing backend runtime dependencies (`pwdlib`, `psycopg2`).
- React production build not run: npm dependency installation is unavailable offline (`ENOTCACHED`).
- Migration SQL/live migration not run: PostgreSQL driver and actual Supabase connection are unavailable.
- Stripe live/test checkout, refund, webhook delivery and SMTP delivery are not claimed as live-verified.

## Known accounting scope limitations
- GST is calculated and posted as a single GST Payable control amount. State-specific CGST/SGST/IGST split and statutory GST return integration are not part of this change.
- Cash Flow endpoint reports cash/bank ledger movements; it does not yet implement a fully classified statutory indirect cash-flow statement.
- Refund endpoint uses the most recent paid Stripe payment intent and limits the refund to that payment's amount.
- Period close currently validates balanced vouchers and Trial Balance; it does not perform automated tax filing, inventory valuation or statutory close checklist reconciliation.
