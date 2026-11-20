"""One-off: move legacy on-disk uploads into Supabase Storage.

    python -m scripts.migrate_local_uploads_to_supabase --source-dir /path/to/old/uploads [--dry-run]

For every document/report row that has no storage_path yet, reads the old local
file (by its stored_filename), uploads it to Supabase Storage, and records the
bucket and path. Rows whose file is missing locally are reported and left
untouched. This is a migration tool only; the running application never reads
local disk. Delete the old folder after verifying the result.
"""

import argparse
from pathlib import Path

from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.config import settings
from app.models import Document, Report
from app.services.storage import (
    DOCUMENTS_PREFIX,
    REPORTS_PREFIX,
    StorageError,
    build_object_path,
    storage,
)

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", required=True, type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not args.dry_run and not settings.storage_configured:
        print("Supabase Storage is not configured.")
        return 1

    moved = skipped = failed = 0
    with SessionLocal() as db:
        jobs = [
            (Document, DOCUMENTS_PREFIX, args.source_dir, lambda r: r.name, lambda r: r.content_type),
            (Report, REPORTS_PREFIX, args.source_dir / "reports", lambda r: f"{r.name}.xlsx", lambda r: XLSX),
        ]
        for model, prefix, folder, name_of, type_of in jobs:
            rows = db.scalars(
                select(model).where(model.storage_path.is_(None), model.stored_filename.is_not(None))
            ).all()
            for row in rows:
                local = folder / row.stored_filename
                if not local.is_file():
                    print(f"SKIP {model.__name__} {row.id}: {local} not found")
                    skipped += 1
                    continue
                path, _ = build_object_path(prefix, row.owner_id, name_of(row))
                if args.dry_run:
                    print(f"WOULD MOVE {model.__name__} {row.id} -> {path}")
                    continue
                try:
                    storage.upload(path, local.read_bytes(), type_of(row))
                    row.storage_bucket = storage.bucket
                    row.storage_path = path
                    db.commit()
                    moved += 1
                    print(f"MOVED {model.__name__} {row.id} -> {path}")
                except (StorageError, Exception) as exc:  # keep going; report at the end
                    db.rollback()
                    failed += 1
                    print(f"FAIL {model.__name__} {row.id}: {exc}")
    print(f"done: moved={moved} skipped={skipped} failed={failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
