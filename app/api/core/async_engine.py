import asyncio
from typing import AsyncGenerator

from engine.models.document import ReasoningTrace


class AsyncEngine:
    def __init__(self, store, kg, pipeline, agent):
        self.store = store          # PostgresStore
        self.kg = kg                # KnowledgeGraph 
        self.pipeline = pipeline
        self.agent = agent

    async def ingest_files(self, files: list[tuple[str, bytes]]) -> list[dict]:
        results = []
        for filename, raw in files:      # one by one, so identical files in a batch can't race
            results.append(await self.pipeline.ingest_file(filename, raw))
        # the pipeline writes straight to Postgres, so reload the in-memory graph
        await self.kg.load()
        return results

    async def list_documents(self):
        return await self.store.list_documents()

    async def get_document(self, doc_id):
        return await self.store.get_document(doc_id)

    async def get_chunks(self, doc_id):
        return await self.store.get_chunks(doc_id)

    async def delete_document(self, doc_id) -> bool:
        deleted = await self.store.delete_document(doc_id)
        if deleted:
            await self.kg.load()
        return deleted

    async def query_stream(
        self,
        question: str,
        confidence_threshold: float | None = None,
        top_k: int | None = None,
        max_depth: int | None = None,
        history: list[dict] | None = None,
    ) -> AsyncGenerator[dict, None]:
        async for event in self.agent.answer_stream(
            question,
            confidence_threshold=confidence_threshold,
            top_k=top_k,
            max_depth=max_depth,
            history=history,
        ):
            yield event

    # ------------------------------------------------------------------
    # Graph reads
    # ------------------------------------------------------------------

    async def refresh_graph(self) -> None:
        await self.kg.load()

    async def get_metrics(self) -> dict:
        return await self.kg.get_metrics()

    async def get_analytics(self, top_k: int = 10) -> dict:
        return await self.kg.get_analytics(top_k)

    async def get_node(self, node_id: str):
        return self.kg.get_node(node_id)

    async def search_nodes(self, query: str, k: int = 5):
        return await self.kg.get_top_k_nodes(query, k)

    async def traverse(self, start_node_id: str, max_depth: int = 2, direction: str = "both"):
        return await asyncio.to_thread(
            self.kg.bfs_traversal, start_node_id, max_depth=max_depth, direction=direction
        )

    async def get_node_edges(self, node_id: str):
        """All edges touching a node, both directions, deduplicated."""
        return self.kg.get_all_edges(node_id)

    async def get_chunk(self, chunk_id: str) -> dict | None:
        row = await self.store.get_chunk(chunk_id)
        if not row:
            return None
        return {
            "id": str(row["id"]),
            "text": row["text"],
            "document_id": str(row["document_id"]),
            "index": row.get("idx", 0),
        }

    async def get_trace_by_id(self, trace_id: str) -> ReasoningTrace | None:
        return await self.kg.get_trace(trace_id)

    async def get_trace_graph(self, trace: ReasoningTrace) -> dict:
        def _build():
            node_ids = set(trace.visited_nodes) | set(trace.entry_nodes)
            nodes = []
            for nid in node_ids:
                n = self.kg.get_node(nid)
                if not n:
                    continue
                nodes.append({
                    "id": n.id,
                    "label": n.name,
                    "type": n.node_type,
                    "description": n.description,
                    "is_entry": nid in trace.entry_nodes,
                })
            edges = [
                {"id": e.id, "source": e.source_id, "target": e.target_id, "label": e.relation}
                for e in trace.traversed_edges
            ]
            return {"nodes": nodes, "edges": edges}

        return await asyncio.to_thread(_build)


    async def get_overview_graph(self, limit: int = 20) -> dict:
        """Default board view: the most-connected entities and the edges between them."""

        def _build():
            central = self.kg.get_central_nodes(top_k=limit)
            node_ids = {nid for nid, _ in central}
            nodes = []
            for nid, _deg in central:
                n = self.kg.get_node(nid)
                if not n:
                    continue
                nodes.append({
                    "id": n.id, "label": n.name, "type": n.node_type,
                    "description": n.description, "is_entry": False,
                })

            seen, edges = set(), []
            for nid in node_ids:
                for e in self.kg.get_all_edges(nid):
                    if e.id in seen or e.source_id not in node_ids or e.target_id not in node_ids:
                        continue
                    seen.add(e.id)
                    edges.append({
                        "id": e.id, "source": e.source_id,
                        "target": e.target_id, "label": e.relation,
                    })
            return {"nodes": nodes, "edges": edges}

        return await asyncio.to_thread(_build)