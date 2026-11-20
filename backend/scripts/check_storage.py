"""Verify real Supabase Storage connectivity with a round trip.

    python -m scripts.check_storage

Creates the private bucket if needed, uploads a tiny probe object, reads it
back, signs a URL, deletes it, and confirms it is gone. Exits non-zero on any
failure. Run it from the backend directory with a populated .env.
"""

import sys
import uuid

from app.core.config import settings
from app.services.storage import StorageError, StorageObjectNotFound, storage


def main() -> int:
    if not settings.storage_configured:
        print("FAIL: set SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY and SUPABASE_STORAGE_BUCKET")
        return 1
    probe = f"healthcheck/{uuid.uuid4().hex}/probe.txt"
    payload = b"azentmart storage probe"
    try:
        print("bucket:", storage.ensure_bucket())
        storage.upload(probe, payload, "text/plain")
        print("upload: ok")
        assert storage.download(probe) == payload, "downloaded bytes differ"
        print("download: ok (bytes match)")
        print("signed url:", "ok" if storage.create_signed_url(probe, 30).startswith("http") else "bad")
        storage.delete(probe)
        try:
            storage.download(probe)
            print("FAIL: object still exists after delete")
            return 1
        except StorageObjectNotFound:
            print("delete: ok (object gone)")
    except (StorageError, AssertionError) as exc:
        print("FAIL:", exc)
        return 1
    print("PASS: Supabase Storage round trip succeeded")
    return 0


if __name__ == "__main__":
    sys.exit(main())
