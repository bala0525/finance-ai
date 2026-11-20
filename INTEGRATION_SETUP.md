# Local integration setup

## 1. Environment

1. Copy `backend/.env.example` to `backend/.env`.
2. Fill the existing database, JWT, Supabase and Gemini settings with your own development values.
3. For Stripe test mode, set `STRIPE_SECRET_KEY` and `STRIPE_WEBHOOK_SECRET`. Keep secret keys backend-only; never put them in React variables.
4. For outbound invoice email, set `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD` and `SMTP_FROM_EMAIL`.
5. Configure `Frontend/.env.local` with `REACT_APP_API_BASE_URL=http://127.0.0.1:8000`.

## 2. Backend setup

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt
alembic upgrade head
python -m app.seed_roles
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Do not run migrations against production until they have been reviewed and tested against a disposable database backup.

## 3. Frontend setup

```bash
cd Frontend
npm ci
npm start
```

## 4. Stripe test mode

1. Use Stripe test-mode API keys only during development.
2. Install and authenticate Stripe CLI separately.
3. Forward events:

```bash
stripe listen --forward-to http://127.0.0.1:8000/payments/stripe/webhook
```

4. Copy the `whsec_...` signing secret printed by the CLI into `STRIPE_WEBHOOK_SECRET` and restart FastAPI.
5. Sign in as the owning Finance User, create an AR sales invoice, submit it, obtain Finance Manager approval, then Administrator final approval.
6. From the Finance User account, use **Pay via Stripe**. Complete the hosted test checkout using a Stripe test payment method shown in Stripe's official test documentation.
7. Confirm that the signed webhook updates the invoice and creates the AR collection journal. Verify the invoice's payment status and General Ledger voucher.

The webhook intentionally rejects unsigned, stale, amount-mismatched, currency-mismatched or unassociated events. A configured Stripe key alone does not prove payment integration is working; the full hosted checkout and webhook flow must be tested.

## 5. AP manual supplier transfer

1. Finance User creates a payment batch from payment-ready AP invoices.
2. Submit the batch; Chief Accountant approves it.
3. Finance User executes the bank transfer outside this application.
4. In the application, record the UTR / bank transaction reference and transfer date, plus optional bank name and proof reference.
5. The backend posts the balanced AP payment journal and marks invoices/batch paid in the same database transaction.

The application does not initiate bank transfers. A payment reference is evidence entered by the Finance User; production operations should verify it against the bank statement before confirming.

## 6. New AR API routes

- `POST /agents/accounts-receivable/sales-invoices` — create a draft (Finance User).
- `GET /agents/accounts-receivable/sales-invoices` — list tenant invoices for Finance roles.
- `POST /agents/accounts-receivable/sales-invoices/{id}/submit` — submit to Finance Manager.
- `POST /agents/accounts-receivable/sales-invoices/{id}/manager-approve` — first approval.
- `POST /agents/accounts-receivable/sales-invoices/{id}/admin-approve` — final approval and invoice number.
- `POST /agents/accounts-receivable/sales-invoices/{id}/reject` — reject with mandatory reason.
- `GET /agents/accounts-receivable/sales-invoices/{id}/pdf` — final invoice PDF.
- `POST /agents/accounts-receivable/sales-invoices/{id}/send-email` — email invoice PDF via SMTP.
- `POST /agents/accounts-receivable/sales-invoices/{id}/stripe-checkout` — create Stripe Checkout Session.
- `POST /payments/stripe/webhook` — unauthenticated Stripe webhook; verifies `Stripe-Signature`.
- `GET /agents/accounts-receivable/sales-invoices/{id}/history` — invoice audit history.

## 7. Important operational limitations in this working pass

- AR GST is currently a single percentage amount; CGST/SGST/IGST selection, place-of-supply logic, HSN/SAC, GST invoice compliance and e-invoice/IRN integration still need implementation.
- Stripe refunds, chargeback/dispute automation and provider settlement reconciliation are not complete.
- SMTP email is synchronous with SENT/FAILED tracking; durable retries/queueing are not yet complete.
- AP proof reference is recorded, but proof-file upload to private Supabase Storage is not yet wired into the UI.
- The full five-role end-to-end test matrix, all-eight-workspace integration tests and production DB migration execution remain outstanding.
