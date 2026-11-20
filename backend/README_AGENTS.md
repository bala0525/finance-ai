# Azentmart Finance AI Backend

This backend preserves the supplied FastAPI application and adds authenticated agent endpoints for the eight Finance AI employees.

## Setup

1. Create a virtual environment and install dependencies:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. Copy `.env.example` to `.env` and set a PostgreSQL `DATABASE_URL`, a long random `SECRET_KEY`, and `GEMINI_API_KEY` for AI document classification, invoice extraction, and Finance Analyst Q&A.

3. Apply existing migrations:

   ```bash
   alembic upgrade head
   ```

4. Start the API from the `backend` directory:

   ```bash
   uvicorn app.main:app --reload
   ```

   Open `/docs` to inspect the OpenAPI schema. `GET /health` is public; finance routes require a bearer access token.

## Eight employee capabilities

| Employee | API |
|---|---|
| AI Accounts Payable | `GET /agents/accounts-payable/dashboard`; existing document invoice review routes `POST /documents/{id}/approve` and `/reject` |
| AI Accounts Receivable | `GET /agents/accounts-receivable/dashboard` |
| AI Invoice Processing | `GET /agents/invoice-processing/dashboard`; existing `POST /documents/upload` and `POST /documents/{id}/reprocess` |
| AI Reconciliation | `GET /agents/reconciliation/dashboard`; `POST /documents/{id}/reconcile`, `GET /documents/{id}/reconciliation` |
| AI Finance Analyst | `POST /agents/finance-analyst/ask` |
| AI Expense Employee | `GET /agents/expense/dashboard` |
| AI Financial Reporting | `GET /agents/financial-reporting/dashboard`; `POST /agents/financial-reporting/generate` |
| AI Fraud Detection | `GET /agents/fraud-detection/dashboard` |

`GET /agents` lists all eight employees and per-agent summary counts.

### Finance Analyst request

```json
{
  "question": "Which uploaded invoices have missing totals?",
  "document_ids": []
}
```

`document_ids` is optional. If omitted, the agent uses up to ten recent, readable documents belonging to the authenticated user. Answers are grounded in extracted document text and include source references. Gemini must be configured.

### Generate a financial summary report

```json
{
  "name": "Finance Summary",
  "period": "October 2026"
}
```

The endpoint saves a completed JSON report record and returns a summary calculated from the user's documents. The summary only includes amounts successfully extracted into document metadata.

## Important data limitations

- AR/AP and expense dashboards summarize uploaded documents and extracted metadata. They are not full ledgers unless the user has uploaded a complete, reliable ledger or source set.
- Fraud Detection returns rule-based review signals (duplicate metadata and unusually high extracted amounts). A signal is not proof of fraud.
- Expense policy compliance is not asserted without configured policy rules.
- Reconciliation requires `.xlsx`/`.xlsm` workbooks with sheets named exactly `Company Cashbook` and `Bank Statement`; the reconciliation engine may still reject workbooks whose transaction columns cannot be parsed.
- AI classification, invoice extraction, and Finance Analyst Q&A require a valid Gemini API key. No API key is included in this ZIP.
- Do not commit `.env`, database passwords, tokens, uploaded customer documents, or production secrets.

## Verification performed for this package

All Python files passed Python bytecode compilation (`compileall`). This is a syntax check, not a claim that database migrations, Gemini requests, or every endpoint have been integration-tested against your own database and frontend.
