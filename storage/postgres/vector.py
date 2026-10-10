import json


class VectorStore:
    def __init__(self, pool):
        self.pool = pool

    async def load_node_embeddings(self) -> dict[str, list[float]]:
        async with self.pool.connection() as conn:
            cur = await conn.execute(
                "SELECT id::text AS id, embedding::text AS embedding FROM nodes WHERE embedding IS NOT NULL"
            )
            return {r["id"]: json.loads(r["embedding"]) for r in await cur.fetchall()}
        
    async def upsert_node_embedding(self, node_id: str, embedding: list[float]) -> None:
        """The node row must already exist (save_node first)."""
        async with self.pool.connection() as conn:
            await conn.execute(
                "UPDATE nodes SET embedding = %s::vector WHERE id = %s::uuid",
                (str(embedding), node_id),
            )

    async def upsert_chunk_embedding(self, chunk_id: str, embedding: list[float]) -> None:
        async with self.pool.connection() as conn:
            await conn.execute(
                "UPDATE chunks SET embedding = %s::vector WHERE id = %s::uuid",
                (str(embedding), chunk_id),
            )

    async def get_node_embedding(self, node_id: str) -> list[float] | None:
        async with self.pool.connection() as conn:
            cur = await conn.execute(
                "SELECT embedding::text AS embedding FROM nodes WHERE id = %s::uuid",
                (node_id,),
            )
            row = await cur.fetchone()
            if not row or row["embedding"] is None:
                return None
            return json.loads(row["embedding"])   # pgvector text form is "[0.1,0.2,...]"

    async def search_nodes(self, query_embedding: list[float], k: int = 5) -> list[tuple[str, float]]:
        vec = str(query_embedding)
        async with self.pool.connection() as conn:
            cur = await conn.execute(
                """SELECT id::text AS id, 1 - (embedding <=> %s::vector) AS score
                   FROM nodes
                   WHERE embedding IS NOT NULL
                   ORDER BY embedding <=> %s::vector
                   LIMIT %s""",
                (vec, vec, k),
            )
            rows = await cur.fetchall()
            return [(r["id"], float(r["score"])) for r in rows]

    async def search_chunks(self, query_embedding: list[float], k: int = 5) -> list[tuple[str, float]]:
        vec = str(query_embedding)
        async with self.pool.connection() as conn:
            cur = await conn.execute(
                """SELECT id::text AS id, 1 - (embedding <=> %s::vector) AS score
                   FROM chunks
                   WHERE embedding IS NOT NULL
                   ORDER BY embedding <=> %s::vector
                   LIMIT %s""",
                (vec, vec, k),
            )
            rows = await cur.fetchall()
            return [(r["id"], float(r["score"])) for r in rows]