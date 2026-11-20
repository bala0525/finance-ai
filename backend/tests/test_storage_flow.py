import io
import os
from pathlib import Path

import pytest
from openpyxl import Workbook

from tests import fake_supabase

BACKEND = Path(__file__).resolve().parents[1]
BUCKET = "test-bucket"


def ap_register() -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.append(["Invoice Number", "Vendor Name", "Invoice Amount", "Invoice Date", "Due Date", "Payment Status"])
    ws.append(["INV-001", "Acme Ltd", 11800, "2026-01-05", "2026-02-05", "Pending"])
    ws.append(["INV-002", "Globex", 5900, "2026-01-07", "2026-02-07", "Paid"])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def recon_workbook() -> bytes:
    wb = Workbook()
    cb = wb.active
    cb.title = "Company Cashbook"
    cb.append(["Date", "Details", "Amount", "Date", "Details", "Amount"])
    cb.append(["2026-01-02", "Payment INV-001", 11800, None, None, None])
    bank = wb.create_sheet("Bank Statement")
    bank.append(["Date", "Description", "Debit", "Credit"])
    bank.append(["2026-01-02", "Payment INV-001", 11800, None])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def tree_snapshot():
    return {str(p) for p in BACKEND.rglob("*") if "__pycache__" not in p.parts and ".pytest_cache" not in p.parts}


def upload(client, headers, name, data, ctype="application/octet-stream"):
    return client.post("/documents/upload", headers=headers, files={"file": (name, data, ctype)})


def test_no_uploads_dir_initially():
    assert not (BACKEND / "uploads").exists()


def test_upload_stores_in_supabase_and_records_metadata(client, users, env):
    before = tree_snapshot()
    data = ap_register()
    r = upload(client, users["alice"], "Q1 Vendor Bills (final).xlsx", data,
               "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    assert r.status_code == 201, r.text
    doc = r.json()
    assert doc["name"] == "Q1 Vendor Bills (final).xlsx"
    assert doc["category"] == "Accounts Payable"  # processed from in-memory bytes

    from app.core.database import SessionLocal
    from app.models import Document
    with SessionLocal() as db:
        row = db.get(Document, doc["id"])
        assert row.storage_bucket == BUCKET
        assert row.storage_path.startswith(f"documents/{row.owner_id}/")
        assert row.storage_path.endswith(".xlsx")
        assert row.size_bytes == len(data)
        assert row.content_type.startswith("application/vnd.openxmlformats")
        assert row.created_at is not None
        stored = env["objects"][(BUCKET, row.storage_path)]
        assert stored["data"] == data
    assert not (BACKEND / "uploads").exists()
    assert tree_snapshot() == before, "upload must not write anything under the backend directory"


def test_same_filename_twice_gets_unique_paths(client, users, env):
    a = upload(client, users["alice"], "dup.csv", b"a,b\n1,2\n").json()
    b = upload(client, users["alice"], "dup.csv", b"a,b\n3,4\n").json()
    from app.core.database import SessionLocal
    from app.models import Document
    with SessionLocal() as db:
        assert db.get(Document, a["id"]).storage_path != db.get(Document, b["id"]).storage_path


def test_download_and_preview_roundtrip(client, users):
    data = ap_register()
    doc = upload(client, users["alice"], "Report ₹ Q2.xlsx", data).json()
    d = client.get(f"/documents/{doc['id']}/file?download=true", headers=users["alice"])
    assert d.status_code == 200 and d.content == data
    cd = d.headers["content-disposition"]
    assert cd.startswith("attachment") and "Report" in cd and ".xlsx" in cd and "UTF-8''Report%20%E2%82%B9%20Q2.xlsx" in cd
    inline = client.get(f"/documents/{doc['id']}/file", headers=users["alice"])
    assert inline.headers["content-disposition"].startswith("inline")
    p = client.get(f"/documents/{doc['id']}/preview", headers=users["alice"]).json()
    assert p["kind"] == "table" and p["sheets"][0]["rows"][1][0] == "INV-001"


def test_csv_preview_and_pdf_preview_kind(client, users):
    csv_doc = upload(client, users["alice"], "x.csv", b"h1,h2\nv1,v2\n").json()
    p = client.get(f"/documents/{csv_doc['id']}/preview", headers=users["alice"]).json()
    assert p["sheets"][0]["rows"] == [["h1", "h2"], ["v1", "v2"]]
    pdf_doc = upload(client, users["alice"], "x.pdf", b"%PDF-1.4 not really a pdf").json()
    assert client.get(f"/documents/{pdf_doc['id']}/preview", headers=users["alice"]).json()["kind"] == "pdf"
    raw = client.get(f"/documents/{pdf_doc['id']}/file", headers=users["alice"])
    assert raw.headers["content-type"] == "application/pdf"


def test_authorization(client, users):
    doc = upload(client, users["alice"], "private.csv", b"a\n1\n").json()
    i = doc["id"]
    assert client.get(f"/documents/{i}/file").status_code in (401, 403)
    assert client.get(f"/documents/{i}/file", headers=users["bob"]).status_code == 404
    assert client.get(f"/documents/{i}/preview", headers=users["bob"]).status_code == 404
    assert client.get(f"/documents/{i}/signed-url", headers=users["bob"]).status_code == 404
    assert client.delete(f"/documents/{i}", headers=users["bob"]).status_code == 404
    assert client.get(f"/documents/{i}/file", headers=users["manager"]).status_code == 200
    # a reviewer can view but not delete someone else's file
    assert client.delete(f"/documents/{i}", headers=users["manager"]).status_code == 403
    assert client.get(f"/documents/{i}/file", headers=users["alice"]).status_code == 200


def test_signed_url(client, users, env):
    data = b"a,b\n1,2\n"
    doc = upload(client, users["alice"], "s.csv", data).json()
    r = client.get(f"/documents/{doc['id']}/signed-url?download=true", headers=users["alice"])
    assert r.status_code == 200
    import httpx
    got = httpx.get(r.json()["url"].split("&download=")[0])
    assert got.status_code == 200 and got.content == data


def test_delete_removes_only_that_object(client, users, env):
    a = upload(client, users["alice"], "keep.csv", b"keep\n1\n").json()
    b = upload(client, users["alice"], "remove.csv", b"remove\n2\n").json()
    from app.core.database import SessionLocal
    from app.models import Document
    with SessionLocal() as db:
        path_a = db.get(Document, a["id"]).storage_path
        path_b = db.get(Document, b["id"]).storage_path
    assert client.delete(f"/documents/{b['id']}", headers=users["alice"]).status_code == 204
    assert (BUCKET, path_b) not in env["objects"]
    assert (BUCKET, path_a) in env["objects"]
    assert client.get(f"/documents/{b['id']}/file", headers=users["alice"]).status_code == 404
    assert client.get(f"/documents/{a['id']}/file", headers=users["alice"]).status_code == 200
    with SessionLocal() as db:
        assert db.get(Document, b["id"]) is None


def test_admin_can_delete_any(client, users):
    doc = upload(client, users["alice"], "adm.csv", b"a\n1\n").json()
    assert client.delete(f"/documents/{doc['id']}", headers=users["admin"]).status_code == 204


def test_delete_refuses_foreign_path(client, users, env):
    doc = upload(client, users["alice"], "tamper.csv", b"a\n1\n").json()
    from app.core.database import SessionLocal
    from app.models import Document
    victim = ("test-bucket", "documents/999/other/file.csv")
    env["objects"][victim] = {"data": b"x", "type": "text/csv"}
    with SessionLocal() as db:
        row = db.get(Document, doc["id"])
        row.storage_path = victim[1]
        db.commit()
    assert client.delete(f"/documents/{doc['id']}", headers=users["alice"]).status_code == 409
    assert victim in env["objects"]


def test_missing_object_gives_clean_404_and_delete_still_works(client, users, env):
    doc = upload(client, users["alice"], "gone.csv", b"a\n1\n").json()
    from app.core.database import SessionLocal
    from app.models import Document
    with SessionLocal() as db:
        env["objects"].pop((BUCKET, db.get(Document, doc["id"]).storage_path))
    r = client.get(f"/documents/{doc['id']}/file", headers=users["alice"])
    assert r.status_code == 404 and "missing" in r.json()["detail"]
    assert client.get(f"/documents/{doc['id']}/preview", headers=users["alice"]).status_code == 404
    assert client.delete(f"/documents/{doc['id']}", headers=users["alice"]).status_code == 204


def test_storage_failure_on_upload_records_nothing_and_no_fallback(client, users, env):
    from app.core.database import SessionLocal
    from app.models import Document
    from sqlalchemy import func, select
    with SessionLocal() as db:
        before = db.scalar(select(func.count(Document.id)))
    env["fail"] = 500
    try:
        before_tree = tree_snapshot()
        r = upload(client, users["alice"], "fail.csv", b"a\n1\n")
        assert r.status_code == 502
        assert tree_snapshot() == before_tree and not (BACKEND / "uploads").exists()
    finally:
        env["fail"] = None
    with SessionLocal() as db:
        assert db.scalar(select(func.count(Document.id))) == before


def test_db_failure_after_upload_removes_orphan(client, users, env, monkeypatch):
    from app.routes import documents as routes
    from sqlalchemy.orm import Session
    objects_before = set(env["objects"])
    real_commit = Session.commit

    def boom(self):
        if any(type(o).__name__ == "Document" for o in self.new):
            raise RuntimeError("db down")
        return real_commit(self)

    monkeypatch.setattr(Session, "commit", boom)
    r = upload(client, users["alice"], "orphan.csv", b"a\n1\n")
    monkeypatch.undo()
    assert r.status_code == 500
    assert set(env["objects"]) == objects_before, "orphaned object must be deleted"


def test_validation(client, users):
    assert upload(client, users["alice"], "bad.exe", b"MZ").status_code == 415
    assert upload(client, users["alice"], "empty.csv", b"").status_code == 400
    assert upload(client, users["alice"], "big.csv", b"x" * (10 * 1024 * 1024 + 1)).status_code == 413


def test_reconciliation_reads_from_storage(client, users):
    doc = upload(client, users["alice"], "recon.xlsx", recon_workbook()).json()
    assert doc["category"] == "Reconciliation"
    r = client.post(f"/documents/{doc['id']}/reconcile", headers=users["alice"])
    assert r.status_code == 200, r.text
    summary = r.json()["summary"]
    assert summary["cashbookTransactionCount"] == 1 and summary["bankTransactionCount"] == 1


def test_reprocess_reads_from_storage(client, users):
    doc = upload(client, users["alice"], "again.xlsx", recon_workbook()).json()
    r = client.post(f"/documents/{doc['id']}/reprocess", headers=users["alice"])
    assert r.status_code == 200 and r.json()["category"] == "Reconciliation"


def test_reports_generate_download_from_storage(client, users, env):
    upload(client, users["alice"], "for-report.xlsx", ap_register())
    r = client.post("/reports/generate", headers=users["alice"], json={"name": "Q1 Report", "period": "Q1"})
    assert r.status_code == 201, r.text
    rep = r.json()
    assert rep["fileAvailable"] is True
    d = client.get(f"/reports/{rep['id']}/download", headers=users["alice"])
    assert d.status_code == 200 and d.content[:2] == b"PK"
    assert 'filename="Q1 Report.xlsx"' in d.headers["content-disposition"]
    assert any(k[1].startswith("reports/") for k in env["objects"])
    assert client.get(f"/reports/{rep['id']}/download", headers=users["bob"]).status_code == 404
    assert not (BACKEND / "uploads").exists()


def test_rag_index_pulls_bytes_from_storage(client, users, env):
    from app.core.database import SessionLocal
    from app.models import Document
    from app.services import rag
    doc = upload(client, users["alice"], "rag.csv", b"vendor,amount\nAcme,100\n").json()
    with SessionLocal() as db:
        row = db.get(Document, doc["id"])
        from app.services.storage import storage
        content = storage.download(row.storage_path)
        from app.services.document_classifier import extract_document_text
        assert "Acme" in extract_document_text(content, ".csv")


def test_unconfigured_storage_is_503_not_fallback(client, users, monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "supabase_service_role_key", "")
    r = upload(client, users["alice"], "nokey.csv", b"a\n1\n")
    assert r.status_code == 503
    assert not (BACKEND / "uploads").exists()


def test_no_local_storage_references_left():
    offenders = []
    for p in (BACKEND / "app").rglob("*.py"):
        text = p.read_text()
        if "upload_path" in text or "UPLOAD_DIR" in text or "upload_dir" in text:
            offenders.append(str(p))
    assert not offenders


def test_check_storage_script_roundtrip(env, capsys):
    from scripts import check_storage
    assert check_storage.main() == 0
    assert "PASS" in capsys.readouterr().out


def test_legacy_migration_script(client, users, env, tmp_path, monkeypatch):
    from sqlalchemy import select
    from app.core.database import SessionLocal
    from app.models import Document, User
    from scripts import migrate_local_uploads_to_supabase as mig

    (tmp_path / "legacy123.csv").write_bytes(b"old,data\n1,2\n")
    with SessionLocal() as db:
        owner = db.scalar(select(User).where(User.email == "alice@example.com"))
        legacy = Document(owner_id=owner.id, name="legacy.csv", stored_filename="legacy123.csv",
                          content_type="text/csv", size_bytes=13)
        db.add(legacy)
        db.commit()
        legacy_id = legacy.id
    monkeypatch.setattr("sys.argv", ["m", "--source-dir", str(tmp_path)])
    assert mig.main() == 0
    r = client.get(f"/documents/{legacy_id}/file?download=true", headers=users["alice"])
    assert r.status_code == 200 and r.content == b"old,data\n1,2\n"
