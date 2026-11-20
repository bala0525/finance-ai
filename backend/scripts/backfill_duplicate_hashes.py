"""Backfill SHA-256 hashes for existing documents stored in Supabase.

Run after the FIN-05 duplicate columns migration:
    python -m app.scripts.backfill_duplicate_hashes

This script never deletes or modifies file contents. It only writes each document's
content hash to the database and skips rows that already have a hash.
"""
import logging

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.document import Document
from app.services.duplicate_detection import sha256_document
from app.services.storage import StorageError, storage

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main() -> int:
    db = SessionLocal()
    processed = skipped = failed = 0
    try:
        documents = db.scalars(select(Document).where(Document.duplicate_hash.is_(None))).all()
        logger.info("Documents requiring hash backfill: %s", len(documents))
        for document in documents:
            if not document.storage_path:
                skipped += 1
                logger.warning("Skipping document %s: no storage path", document.id)
                continue
            try:
                content = storage.download(document.storage_path)
                document.duplicate_hash = sha256_document(content)
                db.commit()
                processed += 1
            except StorageError:
                db.rollback()
                failed += 1
                logger.exception("Could not download document %s for hash backfill", document.id)
            except Exception:
                db.rollback()
                failed += 1
                logger.exception("Could not update hash for document %s", document.id)
        logger.info("Hash backfill result: processed=%s skipped=%s failed=%s", processed, skipped, failed)
        return 1 if failed else 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
