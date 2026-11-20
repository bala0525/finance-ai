"""Supabase Storage access for uploaded documents and generated reports.

Supabase Storage is the single source of truth for file bytes. This module never
touches the local filesystem and never falls back to it: if Storage is not
configured or a call fails, a ``StorageError`` is raised and the caller decides
how to surface it.

The service-role key is used server-side only. The bucket is private; files are
reached through backend-authorised streaming or short-lived signed URLs.
"""

from __future__ import annotations

import logging
import re
import unicodedata
import uuid
from pathlib import PurePosixPath
from urllib.parse import quote

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

# Object keys are generated here; only this root is ever read or deleted.
DOCUMENTS_PREFIX = "documents"
REPORTS_PREFIX = "reports"
MAX_SAFE_NAME_LENGTH = 120


class StorageError(Exception):
    """A Supabase Storage operation failed."""


class StorageNotConfigured(StorageError):
    """Supabase Storage environment variables are missing."""


class StorageObjectNotFound(StorageError):
    """The object does not exist in the bucket."""


def safe_object_name(original_name: str) -> str:
    """ASCII-safe object file name that keeps the original extension."""
    path = PurePosixPath(original_name.replace("\\", "/"))
    extension = path.suffix.lower()
    stem = unicodedata.normalize("NFKD", path.stem).encode("ascii", "ignore").decode()
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", stem).strip("._-") or "file"
    extension = re.sub(r"[^a-z0-9.]", "", extension)
    return f"{stem[:MAX_SAFE_NAME_LENGTH]}{extension}"


def build_object_path(prefix: str, owner_id: int, original_name: str) -> tuple[str, str]:
    """Return ``(object_path, unique_id)``.

    Layout: ``<prefix>/<owner_id>/<uuid>/<safe original name>`` so two uploads of
    the same filename can never collide and the original extension is kept.
    """
    unique_id = uuid.uuid4().hex
    return f"{prefix}/{owner_id}/{unique_id}/{safe_object_name(original_name)}", unique_id


def path_belongs_to(prefix: str, owner_id: int, object_path: str) -> bool:
    """Guard used before deleting: the key must sit under the owner's own folder."""
    expected = f"{prefix}/{owner_id}/"
    return (
        object_path.startswith(expected)
        and ".." not in object_path.split("/")
        and len(object_path) > len(expected)
    )


class SupabaseStorage:
    def __init__(self) -> None:
        self._client: httpx.Client | None = None

    # ------------------------------------------------------------ plumbing
    @property
    def bucket(self) -> str:
        self._require_configured()
        return settings.supabase_storage_bucket

    def _require_configured(self) -> None:
        if not settings.storage_configured:
            raise StorageNotConfigured(
                "Supabase Storage is not configured. Set SUPABASE_URL, "
                "SUPABASE_SERVICE_ROLE_KEY and SUPABASE_STORAGE_BUCKET."
            )

    def _http(self) -> httpx.Client:
        self._require_configured()
        if self._client is None:
            self._client = httpx.Client(
                base_url=f"{settings.supabase_url}/storage/v1",
                headers={
                    "Authorization": f"Bearer {settings.supabase_service_role_key}",
                    "apikey": settings.supabase_service_role_key,
                },
                timeout=settings.storage_timeout_seconds,
            )
        return self._client

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None

    def _object_url(self, object_path: str, *, bucket: str | None = None) -> str:
        return f"/object/{quote(bucket or self.bucket, safe='')}/{quote(object_path, safe='/')}"

    @staticmethod
    def _detail(response: httpx.Response) -> str:
        try:
            body = response.json()
            return str(body.get("message") or body.get("error") or body)[:300]
        except Exception:
            return response.text[:300]

    def _request(self, method: str, url: str, **kwargs) -> httpx.Response:
        try:
            return self._http().request(method, url, **kwargs)
        except StorageError:
            raise
        except httpx.HTTPError as exc:
            logger.error("Supabase Storage request failed: %s %s (%s)", method, url, exc.__class__.__name__)
            raise StorageError("Supabase Storage is unreachable.") from exc

    # ---------------------------------------------------------- operations
    def upload(self, object_path: str, data: bytes, content_type: str | None) -> None:
        """Store bytes at a new key. Never overwrites (``x-upsert: false``)."""
        response = self._request(
            "POST",
            self._object_url(object_path),
            content=data,
            headers={
                "Content-Type": content_type or "application/octet-stream",
                "x-upsert": "false",
                "cache-control": "max-age=3600",
            },
        )
        if response.status_code not in (200, 201):
            logger.error(
                "Supabase upload rejected (%s): %s", response.status_code, self._detail(response)
            )
            raise StorageError(f"Supabase upload failed ({response.status_code}).")

    def download(self, object_path: str) -> bytes:
        response = self._request("GET", self._object_url(object_path))
        if response.status_code in (400, 404):
            # Supabase answers 400 "Object not found" for some missing keys.
            raise StorageObjectNotFound(object_path)
        if response.status_code != 200:
            logger.error(
                "Supabase download failed (%s): %s", response.status_code, self._detail(response)
            )
            raise StorageError(f"Supabase download failed ({response.status_code}).")
        return response.content

    def delete(self, object_path: str) -> None:
        """Delete exactly one object. A missing object counts as already deleted."""
        response = self._request(
            "DELETE",
            f"/object/{quote(self.bucket, safe='')}",
            json={"prefixes": [object_path]},
        )
        if response.status_code not in (200, 204, 404):
            logger.error(
                "Supabase delete failed (%s): %s", response.status_code, self._detail(response)
            )
            raise StorageError(f"Supabase delete failed ({response.status_code}).")

    def create_signed_url(
        self, object_path: str, expires_in: int = 60, download_name: str | None = None
    ) -> str:
        """Short-lived URL for one private object (caller must authorise first)."""
        response = self._request(
            "POST",
            f"/object/sign/{quote(self.bucket, safe='')}/{quote(object_path, safe='/')}",
            json={"expiresIn": int(expires_in)},
        )
        if response.status_code in (400, 404):
            raise StorageObjectNotFound(object_path)
        if response.status_code != 200:
            raise StorageError(f"Supabase could not sign the URL ({response.status_code}).")
        signed = response.json().get("signedURL") or response.json().get("signedUrl")
        if not signed:
            raise StorageError("Supabase returned no signed URL.")
        url = signed if signed.startswith("http") else f"{settings.supabase_url}/storage/v1{signed}"
        if download_name:
            url += f"&download={quote(download_name, safe='')}"
        return url

    def ensure_bucket(self) -> str:
        """Create the private bucket if it does not exist. Returns created|exists."""
        bucket = self.bucket
        response = self._request("GET", f"/bucket/{quote(bucket, safe='')}")
        if response.status_code == 200:
            if response.json().get("public"):
                raise StorageError(
                    f"Bucket '{bucket}' is PUBLIC. Make it private in the Supabase dashboard."
                )
            return "exists"
        created = self._request(
            "POST",
            "/bucket",
            json={"id": bucket, "name": bucket, "public": False, "file_size_limit": 10 * 1024 * 1024},
        )
        if created.status_code not in (200, 201):
            raise StorageError(f"Could not create bucket ({created.status_code}): {self._detail(created)}")
        return "created"


storage = SupabaseStorage()
