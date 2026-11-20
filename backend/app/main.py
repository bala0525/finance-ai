import logging

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.routes.auth import router as auth_router
from app.routes.agents import router as agents_router
from app.routes.documents import router as documents_router
from app.routes.reports import router as reports_router
from app.routes.reconciliation import router as reconciliation_router
from app.routes.users import router as users_router
from app.routes.workflows import router as workflows_router
from app.routes.workflows_more import router as workflows_more_router
from app.routes.ar_sales import router as ar_sales_router
from app.routes.notifications import router as notifications_router
from app.routes.ledger import router as ledger_router
from app.dependencies.permissions import require_agent_workspace_access, require_roles

if not settings.storage_configured:
    logging.getLogger(__name__).warning(
        "Supabase Storage is not configured (SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, "
        "SUPABASE_STORAGE_BUCKET). Uploads and downloads will fail with 503; there is no local fallback."
    )

app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="Backend API for the Azentmart Finance AI platform.",
    docs_url="/docs" if settings.show_docs else None,
    redoc_url="/redoc" if settings.show_docs else None,
    openapi_url="/openapi.json" if settings.show_docs else None,
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
    expose_headers=["Content-Disposition"],
)


app.include_router(auth_router)
app.include_router(agents_router, dependencies=[Depends(require_agent_workspace_access)])
app.include_router(users_router)
app.include_router(documents_router)
app.include_router(reconciliation_router, dependencies=[Depends(require_roles("Finance User", "Finance Manager", "Chief Accountant", "Administrator"))])
app.include_router(reports_router, dependencies=[Depends(require_roles("Finance User", "Finance Manager", "Chief Accountant", "Administrator"))])
app.include_router(workflows_router, dependencies=[Depends(require_agent_workspace_access)])
app.include_router(workflows_more_router, dependencies=[Depends(require_agent_workspace_access)])
app.include_router(ar_sales_router)
app.include_router(notifications_router)
app.include_router(ledger_router)


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "azentmart-finance-ai",
    }
