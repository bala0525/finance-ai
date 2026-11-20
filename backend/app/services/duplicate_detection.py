"""Pure helpers for tenant-scoped invoice duplicate detection."""
import hashlib
import re


def normalize_invoice_number(value: str | None) -> str:
    """Remove punctuation/spacing/case differences from invoice identifiers."""
    if not value:
        return ""
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def normalize_vendor_identity(value: str | None) -> str:
    """Normalize vendor identity conservatively for exact business matching."""
    if not value:
        return ""
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def sha256_document(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()
