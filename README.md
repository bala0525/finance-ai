<<<<<<< HEAD
# Azentmart Finance AI

React 18 / Create React App frontend with a FastAPI, SQLAlchemy, PostgreSQL and Supabase Storage backend.

## Source layout
- `Frontend/` — React application and workspace UI.
- `backend/app/` — FastAPI routes, models, services and role enforcement.
- `backend/alembic/` — database migrations.
- `backend/tests/` — unit and integration tests.
- `IMPLEMENTATION_PLAN.md` — agreed completion roadmap.
- `IMPLEMENTATION_AUDIT.md` — code-level audit and remaining gaps.
- `IMPLEMENTATION_STATUS.md` — changes and validation performed in this pass.
- `INTEGRATION_SETUP.md` — local setup and Stripe/SMTP/AP instructions.

## Quick start
Follow `INTEGRATION_SETUP.md`. Copy `backend/.env.example` to `backend/.env` and `Frontend/.env.example` to `Frontend/.env.local`; fill all credentials locally. Never commit `.env` files.

## Important
This archive is an implementation work-in-progress, not a production-certified release. Stripe and SMTP require credentials and test-mode verification; database migrations must be tested against a disposable PostgreSQL database before deployment. See `IMPLEMENTATION_STATUS.md` for exact validation and unfinished work.
=======
# azentmart-finance-ai
>>>>>>> origin/main
