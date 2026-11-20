"""Retrieval-Augmented Generation for the Finance Analyst.

Pipeline
  1. extract_document_text()  -> raw text of an uploaded document
  2. chunk_text()             -> overlapping passages (~RAG_CHUNK_CHARS)
  3. embed_texts()            -> Gemini embeddings (unit-normalised, 768-d)
  4. stored in document_chunks (per owner)
  5. retrieve()               -> embed the question, cosine-rank the user's
                                 chunks, return the top-k passages

Embeddings are kept as JSON in PostgreSQL and ranked in Python/numpy. That is
fine up to roughly tens of thousands of chunks; beyond that, move the column to
pgvector without changing the callers of this module.
"""

import logging
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from google import genai
from google.genai import types
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.services.document_classifier import extract_document_text
from app.services.storage import StorageError, StorageObjectNotFound, storage

logger = logging.getLogger(__name__)

EMBED_DIMENSIONS = 768
EMBED_BATCH_SIZE = 50
MAX_CHUNKS_PER_DOCUMENT = 300
MAX_UNINDEXED_DOCS_PER_REQUEST = 20
MAX_CHUNKS_SCANNED = 30000


class RagError(Exception):
    """Raised for retrieval/indexing problems that should reach the user."""


@dataclass
class RetrievedChunk:
    document_id: int
    document_name: str
    category: str | None
    chunk_index: int
    content: str
    score: float


# ----------------------------- chunking -----------------------------

def chunk_text(
    text: str,
    chunk_chars: int | None = None,
    overlap: int | None = None,
) -> list[str]:
    """Split text into overlapping chunks, preferring line/sentence boundaries."""
    chunk_chars = chunk_chars or settings.rag_chunk_chars
    overlap = settings.rag_chunk_overlap if overlap is None else overlap
    overlap = min(overlap, chunk_chars // 2)

    text = re.sub(r"[ \t]+", " ", text or "").strip()
    if not text:
        return []

    # Break into units no longer than chunk_chars.
    units: list[str] = []
    for line in re.split(r"\n+", text):
        line = line.strip()
        if not line:
            continue
        while len(line) > chunk_chars:
            cut = max(
                line.rfind(". ", 0, chunk_chars),
                line.rfind(" ", 0, chunk_chars),
            )
            cut = cut + 1 if cut > chunk_chars // 2 else chunk_chars
            units.append(line[:cut].strip())
            line = line[cut:].strip()
        if line:
            units.append(line)

    chunks: list[str] = []
    current = ""

    for unit in units:
        candidate = f"{current}\n{unit}" if current else unit
        if len(candidate) <= chunk_chars:
            current = candidate
            continue

        if current:
            chunks.append(current)
            tail = current[-overlap:] if overlap else ""
            # Start the next chunk on a word boundary inside the overlap.
            if tail and " " in tail:
                tail = tail.split(" ", 1)[1]
            current = f"{tail}\n{unit}".strip() if tail else unit
        else:
            current = unit

    if current:
        chunks.append(current)

    return chunks


# ----------------------------- embeddings -----------------------------

def _normalise(matrix: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return matrix / norms


def embed_texts(texts: list[str], task_type: str) -> np.ndarray:
    """Embed texts with Gemini. Returns a unit-normalised (n, d) float32 array.

    task_type: "RETRIEVAL_DOCUMENT" for passages, "RETRIEVAL_QUERY" for questions.
    """
    if not settings.gemini_api_key:
        raise RagError("Gemini API key is not configured.")

    client = genai.Client(api_key=settings.gemini_api_key)
    vectors: list[list[float]] = []

    for start in range(0, len(texts), EMBED_BATCH_SIZE):
        batch = texts[start:start + EMBED_BATCH_SIZE]
        response = client.models.embed_content(
            model=settings.gemini_embedding_model,
            contents=batch,
            config=types.EmbedContentConfig(
                task_type=task_type,
                output_dimensionality=EMBED_DIMENSIONS,
            ),
        )
        vectors.extend(list(e.values) for e in response.embeddings)

    if len(vectors) != len(texts):
        raise RagError("Embedding service returned an unexpected result.")

    return _normalise(np.asarray(vectors, dtype=np.float32))


# ----------------------------- indexing -----------------------------

def _indexed_document_ids(db: Session, owner_id: int, ids: list[int]) -> set[int]:
    if not ids:
        return set()
    rows = db.execute(
        select(DocumentChunk.document_id)
        .where(
            DocumentChunk.owner_id == owner_id,
            DocumentChunk.document_id.in_(ids),
            DocumentChunk.embedding_model == settings.gemini_embedding_model,
        )
        .group_by(DocumentChunk.document_id)
    ).all()
    return {row[0] for row in rows}


def index_document(db: Session, document: Document, content: bytes) -> int:
    """(Re)build the chunk index of one document from its bytes. Returns the chunk count."""
    text = extract_document_text(content, Path(document.name).suffix)
    chunks = chunk_text(text)[:MAX_CHUNKS_PER_DOCUMENT]

    db.execute(
        delete(DocumentChunk).where(
            DocumentChunk.document_id == document.id,
            DocumentChunk.owner_id == document.owner_id,
        )
    )

    if not chunks:
        db.commit()
        return 0

    vectors = embed_texts(chunks, "RETRIEVAL_DOCUMENT")

    for index, (content, vector) in enumerate(zip(chunks, vectors)):
        db.add(
            DocumentChunk(
                document_id=document.id,
                owner_id=document.owner_id,
                chunk_index=index,
                content=content,
                embedding=[float(x) for x in vector],
                embedding_model=settings.gemini_embedding_model,
            )
        )

    db.commit()
    return len(chunks)


def ensure_indexed(
    db: Session,
    documents: list[Document],
) -> dict:
    """Index documents that have no chunks yet (lazy indexing on first question)."""
    if not documents:
        return {"indexedNow": 0, "pending": 0, "failed": []}

    owner_id = documents[0].owner_id
    already = _indexed_document_ids(db, owner_id, [d.id for d in documents])
    todo = [d for d in documents if d.id not in already]

    indexed_now = 0
    failed: list[str] = []

    for document in todo[:MAX_UNINDEXED_DOCS_PER_REQUEST]:
        if not document.storage_path:
            failed.append(f"{document.name} (file missing)")
            continue
        try:
            content = storage.download(document.storage_path)
        except StorageObjectNotFound:
            failed.append(f"{document.name} (file missing)")
            continue
        except StorageError:
            logger.warning("Storage read failed for document %s", document.id, exc_info=True)
            failed.append(f"{document.name} (storage unavailable)")
            continue
        try:
            count = index_document(db, document, content)
            if count:
                indexed_now += 1
        except RagError:
            raise
        except Exception:
            db.rollback()
            logger.warning("Indexing failed for document %s", document.id, exc_info=True)
            failed.append(document.name)

    pending = max(0, len(todo) - MAX_UNINDEXED_DOCS_PER_REQUEST)
    return {"indexedNow": indexed_now, "pending": pending, "failed": failed}


# ----------------------------- retrieval -----------------------------

def retrieve(
    db: Session,
    owner_id: int,
    question: str,
    document_ids: list[int] | None = None,
    top_k: int | None = None,
) -> list[RetrievedChunk]:
    """Return the top-k passages (cosine similarity) for the owner's documents."""
    top_k = top_k or settings.rag_top_k

    statement = (
        select(DocumentChunk, Document.name, Document.category)
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(
            DocumentChunk.owner_id == owner_id,
            DocumentChunk.embedding_model == settings.gemini_embedding_model,
        )
        .limit(MAX_CHUNKS_SCANNED)
    )
    if document_ids:
        statement = statement.where(DocumentChunk.document_id.in_(document_ids))

    rows = db.execute(statement).all()
    if not rows:
        return []

    matrix = np.asarray([row[0].embedding for row in rows], dtype=np.float32)
    query = embed_texts([question], "RETRIEVAL_QUERY")[0]

    if matrix.shape[1] != query.shape[0]:
        raise RagError(
            "Stored embeddings do not match the current embedding model. "
            "Re-index the documents."
        )

    scores = matrix @ query
    order = np.argsort(-scores)[:top_k]

    return [
        RetrievedChunk(
            document_id=rows[i][0].document_id,
            document_name=rows[i][1],
            category=rows[i][2],
            chunk_index=rows[i][0].chunk_index,
            content=rows[i][0].content,
            score=float(scores[i]),
        )
        for i in order
    ]


def count_indexed_chunks(db: Session, owner_id: int) -> int:
    return db.scalar(
        select(func.count(DocumentChunk.id)).where(DocumentChunk.owner_id == owner_id)
    ) or 0
