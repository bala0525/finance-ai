"""Test harness: embedded PostgreSQL (pgserver) + fake Supabase Storage server.

The real FastAPI app, real Alembic migrations and real database are used; only
Supabase Storage is replaced by tests/fake_supabase.py.
"""

import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

import pytest
import uvicorn

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def env():
    import pgserver

    pgdir = tempfile.mkdtemp(prefix="pg_")
    pg = pgserver.get_server(pgdir, cleanup_mode="stop")
    uri = pg.get_uri().replace("postgresql://", "postgresql://", 1)

    from tests import fake_supabase

    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(fake_supabase.app, host="127.0.0.1", port=port, log_level="error"))
    threading.Thread(target=server.run, daemon=True).start()
    while not server.started:
        time.sleep(0.05)

    os.environ.update(
        DATABASE_URL=uri,
        SECRET_KEY="x" * 40,
        APP_ENV="development",
        SUPABASE_URL=f"http://127.0.0.1:{port}",
        SUPABASE_ANON_KEY="anon",
        SUPABASE_SERVICE_ROLE_KEY=fake_supabase.SERVICE_KEY,
        SUPABASE_STORAGE_BUCKET="test-bucket",
    )
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=BACKEND, check=True, env=os.environ.copy())
    from app.seed_roles import seed_roles

    seed_roles()
    yield fake_supabase.STATE
    server.should_exit = True
    pg.cleanup()


@pytest.fixture(scope="session")
def client(env):
    from fastapi.testclient import TestClient
    from app.main import app

    with TestClient(app) as c:
        yield c


def make_user(client, email, role=None):
    r = client.post("/auth/signup", json={"email": email, "password": "Passw0rd!123", "full_name": "Test User"})
    assert r.status_code == 201, r.text
    if role:
        from sqlalchemy import select
        from app.core.database import SessionLocal
        from app.models import Role, User

        with SessionLocal() as db:
            user = db.scalar(select(User).where(User.email == email))
            user.role_id = db.scalar(select(Role).where(Role.name == role)).id
            db.commit()
    token = client.post("/auth/login", json={"email": email, "password": "Passw0rd!123"}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="session")
def users(client):
    return {
        "alice": make_user(client, "alice@example.com"),
        "bob": make_user(client, "bob@example.com"),
        "manager": make_user(client, "mgr@example.com", "Finance Manager"),
        "admin": make_user(client, "admin@example.com", "Administrator"),
    }
