import asyncio
import hashlib
import os

from engine.ingestion.chunking import chunk_document
from engine.ingestion.loader import SUPPORTED, load_text



def _prepare(suffix: str, raw: bytes):
    """CPU work: runs in a side thread."""
    content = load_text(suffix, raw)
    if not content.strip():
        return None, None, []
    return content, hashlib.sha256(raw).hexdigest(), chunk_document(content)


class IngestionPipeline:
    def __init__(self, store,encoder):
        self.store = store
        self.encoder =encoder

    async def ingest_file(self, filename: str, raw: bytes) -> dict:
        name = os.path.basename(filename or "")
        suffix = os.path.splitext(name)[1].lower()

        if suffix not in SUPPORTED:
            return self._result(name, "skipped", reason="unsupported type")

        try:
            content, checksum, chunks = await asyncio.to_thread(_prepare, suffix, raw)
        except Exception:
            return self._result(name, "skipped", reason="could not read file")

        if not chunks:
            return self._result(name, "skipped",
                                reason="no text found (scanned PDF or empty file)")

        existing = await self.store.get_by_checksum(checksum)
        if existing:
            return self._result(name, "duplicate", doc_id=existing["id"])

        texts = [f"{h}\n{t}" if h else t for h, t in chunks]
        embeddings = await asyncio.to_thread(self.encoder.encode, texts)

        doc = await self.store.save_document_with_chunks(name, content, checksum, chunks,embeddings)
        return self._result(name, "saved", doc_id=doc["id"], chunks=doc["chunk_count"])

    @staticmethod
    def _result(name, status, doc_id=None, reason=None, chunks=0) -> dict:
        return {"id": str(doc_id) if doc_id else None, "name": name,
                "status": status, "reason": reason, "chunks": chunks}