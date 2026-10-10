from psycopg.types.json import Jsonb


class GraphStore:
    def __init__(self, pool):
        self.pool = pool

    # ---------- nodes ----------

    async def load_nodes(self) -> list[dict]:
        async with self.pool.connection() as conn:
            cur = await conn.execute(
                """SELECT id::text AS id, name, node_type, aliases, description,
                          source_chunk_ids::text[] AS source_chunk_ids, created_at
                   FROM nodes"""
            )
            return await cur.fetchall()

    async def save_node(self, node_id: str, name: str, node_type: str,
                        aliases: list[str], description: str,
                        source_chunk_ids: list[str]) -> None:
        """Insert or update. Embedding is written separately by VectorStore."""
        async with self.pool.connection() as conn:
            await conn.execute(
                """INSERT INTO nodes (id, name, node_type, aliases, description, source_chunk_ids)
                   VALUES (%s::uuid, %s, %s, %s, %s, %s::uuid[])
                   ON CONFLICT (id) DO UPDATE SET
                       name = EXCLUDED.name,
                       node_type = EXCLUDED.node_type,
                       aliases = EXCLUDED.aliases,
                       description = EXCLUDED.description,
                       source_chunk_ids = EXCLUDED.source_chunk_ids""",
                (node_id, name, node_type, aliases, description, source_chunk_ids),
            )

    async def delete_node(self, node_id: str) -> None:
        """Edges are removed by ON DELETE CASCADE."""
        async with self.pool.connection() as conn:
            await conn.execute("DELETE FROM nodes WHERE id = %s::uuid", (node_id,))

    # ---------- edges ----------

    async def load_edges(self) -> list[dict]:
        async with self.pool.connection() as conn:
            cur = await conn.execute(
                """SELECT id::text AS id, source_id::text AS source_id,
                          target_id::text AS target_id, relation,
                          source_chunk_id::text AS source_chunk_id, created_at
                   FROM edges"""
            )
            return await cur.fetchall()

    async def save_edge(self, edge_id: str, source_id: str, target_id: str,
                        relation: str, source_chunk_id: str | None) -> bool:
        """True if inserted, False if it already existed."""
        async with self.pool.connection() as conn:
            cur = await conn.execute(
                """INSERT INTO edges (id, source_id, target_id, relation, source_chunk_id)
                   VALUES (%s::uuid, %s::uuid, %s::uuid, %s, %s::uuid)
                   ON CONFLICT (source_id, target_id, relation) DO NOTHING
                   RETURNING id""",
                (edge_id, source_id, target_id, relation, source_chunk_id),
            )
            return (await cur.fetchone()) is not None

    # ---------- traces ----------

    async def save_trace(self, question: str, entry_nodes: list[str],
                         visited_nodes: list[str], traversed_edges: list[dict],
                         source_chunks: list[str], confidence: float) -> str:
        async with self.pool.connection() as conn:
            cur = await conn.execute(
                """INSERT INTO traces (question, entry_nodes, visited_nodes,
                                       traversed_edges, source_chunks, confidence)
                   VALUES (%s, %s::uuid[], %s::uuid[], %s, %s::uuid[], %s)
                   RETURNING id::text AS id""",
                (question, entry_nodes, visited_nodes, Jsonb(traversed_edges),
                 source_chunks, confidence),
            )
            row = await cur.fetchone()
            return row["id"]

    async def get_trace(self, trace_id: str) -> dict | None:
        async with self.pool.connection() as conn:
            cur = await conn.execute(
                """SELECT id::text AS id, question,
                          entry_nodes::text[] AS entry_nodes,
                          visited_nodes::text[] AS visited_nodes,
                          traversed_edges,
                          source_chunks::text[] AS source_chunks,
                          confidence, created_at
                   FROM traces WHERE id = %s::uuid""",
                (trace_id,),
            )
            return await cur.fetchone()

    async def load_traces_for_question(self, question: str) -> list[dict]:
        async with self.pool.connection() as conn:
            cur = await conn.execute(
                """SELECT id::text AS id, question,
                          entry_nodes::text[] AS entry_nodes,
                          visited_nodes::text[] AS visited_nodes,
                          traversed_edges,
                          source_chunks::text[] AS source_chunks,
                          confidence, created_at
                   FROM traces WHERE question = %s ORDER BY created_at DESC""",
                (question,),
            )
            return await cur.fetchall()

    # ---------- analytics (SQL functions from schemas.sql) ----------

    async def get_analytics(self, top_k: int = 10) -> dict:
        async with self.pool.connection() as conn:
            cur = await conn.execute("SELECT * FROM graph_metrics()")
            metrics = await cur.fetchone()

            cur = await conn.execute("SELECT * FROM graph_node_type_distribution()")
            node_types = await cur.fetchall()

            cur = await conn.execute("SELECT * FROM graph_relation_distribution(%s)", (top_k,))
            relations = await cur.fetchall()

            cur = await conn.execute(
                "SELECT id::text AS id, label, type, value FROM graph_top_nodes_by_degree(%s)",
                (top_k,),
            )
            top_nodes = await cur.fetchall()

            cur = await conn.execute("SELECT * FROM graph_degree_distribution()")
            degrees = await cur.fetchall()

            cur = await conn.execute(
                """SELECT id::text AS id, label, chunks, entities, ingested_at
                   FROM graph_document_stats()"""
            )
            documents = await cur.fetchall()

        return {
            "metrics": metrics,
            "node_types": node_types,
            "relations": relations,
            "top_nodes": top_nodes,
            "degree_distribution": degrees,
            "documents": [
                {**d, "ingested_at": d["ingested_at"].isoformat() if d["ingested_at"] else None}
                for d in documents
            ],
        }
    
    async def get_metrics(self) -> dict:
        async with self.pool.connection() as conn:
            cur = await conn.execute("SELECT * FROM graph_metrics()")
            return await cur.fetchone()