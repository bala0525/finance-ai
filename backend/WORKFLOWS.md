# AI employee workflows (added features)

Migration: `e5a1c7b9d3f2` (run `alembic upgrade head`). New tables have Row Level Security enabled like the rest.
No new environment variables, except the optional `CORS_ORIGINS` (comma separated extra browser origins).

**Rules used everywhere:** every number is calculated in Python from uploaded documents or the imported ledger.
Gemini only (a) extracts invoice fields, (b) chooses a GL account *from your own chart*, and (c) writes optional
wording/commentary that is labelled "AI". Calculations never come from the model.

| Employee | Endpoints (under `/agents`) | Notes |
|---|---|---|
| AP | `GET accounts-payable/exceptions`, `POST .../exceptions/resolve`, `GET .../payment-ready`, `GET/POST .../payment-batches`, `GET .../payment-batches/{id}/export`, `POST .../{id}/mark-paid` (Admin / Finance Manager), `POST .../{id}/cancel` | Batch = approved + valid + non-duplicate invoices; one invoice can be in one batch. Paying a batch sets its invoices to `PAID`. |
| AR | `GET accounts-receivable/priorities`, `GET .../cash-forecast?delay_days=`, `GET/POST .../reminders[/generate]`, `POST .../reminders/{id}/mark-sent`, `GET/POST/PATCH .../disputes`, `POST .../documents/{id}/collected` | Reminders are drafts only. No email is sent. |
| Invoice Processing | `GET/POST invoice-processing/chart-of-accounts[/load-default]`, `POST .../documents/{id}/coding/suggest`, `POST .../coding/accept` | Extraction confidence is stored on the document (`extractionConfidence`, `fieldConfidence`, `lowConfidence` < 0.75). |
| Reconciliation | `GET reconciliation/{doc}/exceptions`, `POST .../exceptions/resolve`, `GET .../statement` | Cases are derived from the latest run; resolutions are stored per item. |
| Finance Analyst | `POST finance-analyst/{insights,variance,forecast,scenario}` | Insights = 8 fixed rules (spend trend, vendor concentration, overdue receivables, payables due soon, approval backlog, data quality, largest items, net position). Moving average / linear trend only. Returns "Insufficient data" instead of guessing. |
| Expense | `GET/PUT expense/policies`, `GET expense/evaluation`, `POST expense/decision` | Default limits are starter values and are labelled as defaults until edited. Decisions are recorded in the document history. |
| Financial Reporting | `GET/POST financial-reporting/ledger[/template|/import]`, `POST .../statements`, `GET .../statements/export`, `GET/POST .../schedules`, `POST .../schedules/{id}/{pause|resume|run}` | P&L / BS / CF come from the imported ledger (`Accounts` + `Journal` sheets). Import REPLACES the user's ledger. Schedules run on demand; there is no background job. |
| Fraud | `GET fraud-detection/risk`, `GET fraud-detection/evidence/{doc}` (Admin / Finance Manager) | 0-100 score from `RULE_WEIGHTS` in `app/services/fraud_scoring.py`. Not proof of fraud. |

## Known limits
- Cash flow uses the indirect method with name-based account classification and no depreciation adjustment. Any gap is shown as "unexplained difference".
- Ledger data is per user (a Finance Manager sees their own ledger, not other users').
- AR "collected" is a manual action; there is no bank feed.
