"""
Knowledge Graph: in-memory graph cache + Postgres persistence.
Nodes, edges and node embeddings are cached in memory for traversal;
everything else (chunks, documents, analytics, traces) goes to Postgres.
"""

import asyncio
from collections import defaultdict

from storage.postgres.graph import GraphStore
from storage.postgres.vector import VectorStore
from engine.embedding.encoder import EmbeddingEncoder
from engine.models.node import Node
from engine.models.edge import Edge
from engine.models.document import ReasoningTrace
from engine.graph.traversal import TraversalEngine


def _iso(v) -> str:
    """DB returns datetime objects; the models expect ISO strings."""
    return v.isoformat() if hasattr(v, "isoformat") else str(v)


class KnowledgeGraph:

    def __init__(
        self,
        store: GraphStore,
        vector_store: VectorStore,
        encoder: EmbeddingEncoder,
        min_entry_score: float = 0.35,
        guided_traversal_min_score: float = 0.20,
        beam_width: int = 3,
    ):
        self.store = store
        self.vector_store = vector_store
        self.encoder = encoder
        self.min_entry_score = min_entry_score
        self.guided_traversal_min_score = guided_traversal_min_score
        self.beam_width = beam_width

        self.traversal = TraversalEngine(
            guided_min_score=guided_traversal_min_score,
            beam_width=beam_width,
            min_entry_score=min_entry_score,
        )

        self.nodes: dict[str, Node] = {}
        self.out_edges: dict[str, list[Edge]] = defaultdict(list)
        self.in_edges: dict[str, list[Edge]] = defaultdict(list)
        self._embedding_cache: dict[str, list[float]] = {}

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    async def load(self) -> None:
        """(Re)load nodes, edges and node embeddings from Postgres."""
        node_rows = await self.store.load_nodes()
        edge_rows = await self.store.load_edges()
        embeddings = await self.vector_store.load_node_embeddings()

        nodes = {
            r["id"]: Node.from_dict({**r, "created_at": _iso(r["created_at"])})
            for r in node_rows
        }

        out_edges: dict[str, list[Edge]] = defaultdict(list)
        in_edges: dict[str, list[Edge]] = defaultdict(list)
        for r in edge_rows:
            e = Edge.from_dict({**r, "created_at": _iso(r["created_at"])})
            out_edges[e.source_id].append(e)
            in_edges[e.target_id].append(e)

        # Swap in at the end so readers never see a half-loaded graph
        self.nodes = nodes
        self.out_edges = out_edges
        self.in_edges = in_edges
        self._embedding_cache = embeddings

    # ------------------------------------------------------------------
    # Node operations
    # ------------------------------------------------------------------

    async def add_node(self, node: Node) -> str:
        await self.store.save_node(
            node.id, node.name, node.node_type,
            node.aliases, node.description, node.source_chunk_ids,
        )
        emb = await asyncio.to_thread(
            self.encoder.encode_single, f"{node.name} {node.description}".strip()
        )
        await self.vector_store.upsert_node_embedding(node.id, emb)
        self.nodes[node.id] = node
        self._embedding_cache[node.id] = emb
        return node.id

    def get_node(self, node_id: str) -> Node | None:
        return self.nodes.get(node_id)

    async def update_node_chunks(self, node_id: str, new_chunk_id: str) -> bool:
        """Add a new source chunk to an existing node (for dedup merges)."""
        node = self.nodes.get(node_id)
        if node is None:
            return False
        if new_chunk_id not in node.source_chunk_ids:
            node.source_chunk_ids.append(new_chunk_id)
            await self.store.save_node(
                node.id, node.name, node.node_type,
                node.aliases, node.description, node.source_chunk_ids,
            )
        return True

    def get_nodes_by_type(self, node_type: str) -> list[Node]:
        nt = node_type.upper()
        return [n for n in self.nodes.values() if n.node_type.upper() == nt]

    async def delete_node(self, node_id: str) -> None:
        """Remove a node and all its edges (edges cascade in the DB)."""
        if node_id not in self.nodes:
            return
        await self.store.delete_node(node_id)
        del self.nodes[node_id]
        self._embedding_cache.pop(node_id, None)

        self.out_edges.pop(node_id, None)
        self.in_edges.pop(node_id, None)
        for src, edges in self.out_edges.items():
            self.out_edges[src] = [e for e in edges if e.target_id != node_id]
        for tgt, edges in self.in_edges.items():
            self.in_edges[tgt] = [e for e in edges if e.source_id != node_id]

    # ------------------------------------------------------------------
    # Edge operations
    # ------------------------------------------------------------------

    async def create_edge(self, edge: Edge) -> bool:
        """Add an edge. Returns True if new, False if duplicate."""
        if edge.source_id not in self.nodes or edge.target_id not in self.nodes:
            raise ValueError(
                f"Edge references non-existent node: {edge.source_id} -> {edge.target_id}"
            )
        if edge.source_id == edge.target_id:
            raise ValueError("Self-loops are not allowed")

        inserted = await self.store.save_edge(
            edge.id, edge.source_id, edge.target_id, edge.relation, edge.source_chunk_id
        )
        if inserted:
            self.out_edges[edge.source_id].append(edge)
            self.in_edges[edge.target_id].append(edge)
        return inserted

    def get_outgoing_edges(self, node_id: str) -> list[Edge]:
        return list(self.out_edges.get(node_id, []))

    def get_incoming_edges(self, node_id: str) -> list[Edge]:
        return list(self.in_edges.get(node_id, []))

    def get_all_edges(self, node_id: str) -> list[Edge]:
        """All edges touching node_id (both directions), deduplicated."""
        seen, result = set(), []
        for e in self.out_edges.get(node_id, []) + self.in_edges.get(node_id, []):
            if e.id not in seen:
                seen.add(e.id)
                result.append(e)
        return result

    def get_edges_between(self, source_id: str, target_id: str) -> list[Edge]:
        return [e for e in self.out_edges.get(source_id, []) if e.target_id == target_id]

    def edge_exists(self, source_id: str, target_id: str, relation: str) -> bool:
        return any(
            e.target_id == target_id and e.relation == relation
            for e in self.out_edges.get(source_id, [])
        )

    # ------------------------------------------------------------------
    # Retrieval (pgvector)
    # ------------------------------------------------------------------

    async def get_top_k_nodes(self, query: str, k: int = 5) -> list[tuple[str, float]]:
        """Returns (node_id, similarity) sorted descending."""
        emb = await asyncio.to_thread(self.encoder.encode_single, query)
        return await self.vector_store.search_nodes(emb, k=k)

    async def search_chunks(self, query: str, k: int = 5) -> list[tuple[str, float]]:
        emb = await asyncio.to_thread(self.encoder.encode_single, query)
        return await self.vector_store.search_chunks(emb, k=k)

    def _get_node_embedding(self, node_id: str) -> list[float] | None:
        # Sync on purpose: the traversal loop calls this. The cache is preloaded in load().
        return self._embedding_cache.get(node_id)

    # ------------------------------------------------------------------
    # Traversal
    # ------------------------------------------------------------------

    def bfs_traversal(self, start_node_id: str, **kwargs) -> tuple[set[str], list[Edge]]:
        return self.traversal.bfs(
            start_node_id=start_node_id,
            nodes=self.nodes,
            out_edges=self.out_edges,
            in_edges=self.in_edges,
            **kwargs,
        )

    async def guided_traversal(
        self,
        start_node_id: str,
        query: str,
        max_depth: int = 2,
        direction: str = "both",
    ) -> tuple[set[str], list[Edge], list[float]]:
        query_emb = await asyncio.to_thread(self.encoder.encode_single, query)
        return self.traversal.guided(
            start_node_id=start_node_id,
            query_emb=query_emb,
            nodes=self.nodes,
            out_edges=self.out_edges,
            in_edges=self.in_edges,
            min_score=self.guided_traversal_min_score,
            get_embedding=self._get_node_embedding,
            max_depth=max_depth,
            direction=direction,
        )

    async def multi_hop_query(
        self,
        question: str,
        top_k: int = 3,
        max_depth: int = 2,
        direction: str = "both",
        min_score: float | None = None,
    ) -> ReasoningTrace:
        """
        `min_score`, when provided, overrides the instance-level
        `guided_traversal_min_score` for just this call (used by the chat
        panel's confidence threshold).
        """
        query_emb = await asyncio.to_thread(self.encoder.encode_single, question)
        entry_nodes = await self.vector_store.search_nodes(query_emb, k=top_k)

        # TraversalEngine is sync, so do the one async lookup it may need up front
        chunk_fallback: list[tuple[str, float]] = []
        if not any(score >= self.min_entry_score for _, score in entry_nodes):
            chunk_fallback = await self.vector_store.search_chunks(query_emb, k=5)

        return await asyncio.to_thread(
            self.traversal.multi_hop,
            question=question,
            query_emb=query_emb,
            entry_nodes_with_scores=entry_nodes,
            nodes=self.nodes,
            out_edges=self.out_edges,
            in_edges=self.in_edges,
            get_embedding=self._get_node_embedding,
            search_chunks=lambda q, k: chunk_fallback,
            max_depth=max_depth,
            direction=direction,
            guided_min_score=(
                min_score if min_score is not None else self.guided_traversal_min_score
            ),
        )

    # ------------------------------------------------------------------
    # Metrics / analytics (SQL functions in schemas.sql)
    # ------------------------------------------------------------------

    async def get_metrics(self) -> dict:
        return await self.store.get_metrics()

    async def get_analytics(self, top_k: int = 10) -> dict:
        return await self.store.get_analytics(top_k)

    def get_central_nodes(self, top_k: int = 10) -> list[tuple[str, int]]:
        """Nodes sorted by total degree (in-memory, used by the overview graph)."""
        degrees = [
            (nid, len(self.out_edges.get(nid, [])) + len(self.in_edges.get(nid, [])))
            for nid in list(self.nodes)
        ]
        degrees.sort(key=lambda x: x[1], reverse=True)
        return degrees[:top_k]

    # ------------------------------------------------------------------
    # Trace persistence
    # ------------------------------------------------------------------

    async def save_trace(self, trace: ReasoningTrace) -> str:
        return await self.store.save_trace(
            trace.question,
            trace.entry_nodes,
            trace.visited_nodes,
            [e.to_dict() for e in trace.traversed_edges],
            trace.source_chunks,
            trace.confidence,
        )

    async def get_trace(self, trace_id: str) -> ReasoningTrace | None:
        row = await self.store.get_trace(trace_id)
        return ReasoningTrace.from_dict(row) if row else None

    async def get_past_traces(self, question: str) -> list[ReasoningTrace]:
        rows = await self.store.load_traces_for_question(question)
        return [ReasoningTrace.from_dict(r) for r in rows]
    