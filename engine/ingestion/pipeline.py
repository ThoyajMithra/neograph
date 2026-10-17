import asyncio
import hashlib
import os

from engine.ingestion.chunking import chunk_document
from engine.ingestion.loader import SUPPORTED, load_text


# One graph build at a time across all requests. The pipeline object is created per
# request, so the lock has to live at module level to be shared. Without it, two
# uploads could both miss the same entity and create it twice.
_graph_lock = asyncio.Lock()


def _prepare(suffix: str, raw: bytes):
    """CPU work: runs in a side thread."""
    content = load_text(suffix, raw)
    if not content.strip():
        return None, None, []
    return content, hashlib.sha256(raw).hexdigest(), chunk_document(content)


class IngestionPipeline:
    def __init__(self, store, encoder, kg=None, extractor=None, concurrency: int | None = None):
        self.store = store
        self.encoder = encoder
        self.kg = kg
        self.extractor = extractor
        self.concurrency = concurrency or int(os.getenv("EXTRACT_CONCURRENCY", "4"))

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

        doc = await self.store.save_document_with_chunks(name, content, checksum, chunks, embeddings)

        # NEW: graph step. The document is already saved, so a failure here loses nothing.
        graph = {"entities": 0, "relations": 0}
        if self.kg is not None and self.extractor is not None:
            try:
                async with _graph_lock:
                    graph = await self._build_graph(doc["id"])
            except Exception as e:
                print(f"Graph build failed for '{name}': {e}")

        return self._result(name, "saved", doc_id=doc["id"], chunks=doc["chunk_count"],
                            entities=graph["entities"], relations=graph["relations"])

    # NEW
    async def _build_graph(self, doc_id) -> dict:
        rows = await self.store.get_chunks(doc_id)      # id, idx, heading, text (in idx order)

        # Phase 1: LLM calls, a few at a time
        sem = asyncio.Semaphore(self.concurrency)

        async def run(row):
            text = f"{row['heading']}\n{row['text']}" if row["heading"] else row["text"]
            async with sem:
                return row, await self.extractor.extract_raw(text)

        results = await asyncio.gather(*(run(r) for r in rows))

        # Phase 2: one chunk at a time, so dedup always sees what earlier chunks added
        n_entities = n_relations = 0
        for row, parsed in results:
            if parsed is None:
                continue
            chunk_id = str(row["id"])

            nodes, edges = await self.extractor.resolve(
                parsed, chunk_id,
                existing_nodes=dict(self.kg.nodes),               # snapshot, safe to read in a thread
                get_embedding=self.kg._get_node_embedding,
            )

            for node in nodes:
                if node.id in self.kg.nodes:                      # merged: just link this chunk
                    await self.kg.update_node_chunks(node.id, chunk_id)
                else:
                    await self.kg.add_node(node)
                    n_entities += 1

            for edge in edges:
                try:
                    if await self.kg.create_edge(edge):
                        n_relations += 1
                except ValueError:
                    continue                                       # endpoint missing, skip

        return {"entities": n_entities, "relations": n_relations}

    @staticmethod
    def _result(name, status, doc_id=None, reason=None, chunks=0,
                entities=0, relations=0) -> dict:
        return {"id": str(doc_id) if doc_id else None, "name": name,
                "status": status, "reason": reason, "chunks": chunks,
                "entities": entities, "relations": relations}