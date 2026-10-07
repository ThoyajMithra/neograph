from psycopg.types.json import Jsonb


class Chat:
    def __init__(self, pool):
        self.pool = pool

    async def save_turn(self, question: str, answer: str, sources: list,
                        confidence: float, latency_ms: float) -> None:
        async with self.pool.connection() as conn:
            await conn.execute(
                """INSERT INTO chat_messages (question, answer, sources, confidence, latency_ms)
                   VALUES (%s, %s, %s, %s, %s)""",
                (question, answer, Jsonb(sources), confidence, latency_ms),
            )

    async def search_chunks_vector(self, query_embedding: list[float], limit: int = 5) -> list[dict]:
        """Meaning search. <=> is pgvector's cosine distance (smaller = closer)."""
        vec = str(query_embedding)
        async with self.pool.connection() as conn:
            cur = await conn.execute(
                """SELECT c.id, c.document_id, d.name AS document_name,
                          c.idx, c.heading, c.text,
                          1 - (c.embedding <=> %s::vector) AS score
                   FROM chunks c
                   JOIN documents d ON d.id = c.document_id
                   WHERE c.embedding IS NOT NULL
                   ORDER BY c.embedding <=> %s::vector
                   LIMIT %s""",
                (vec, vec, limit),
            )
            return await cur.fetchall()


    async def list_turns(self, limit: int = 50) -> list[dict]:
        async with self.pool.connection() as conn:
            cur = await conn.execute(
                """SELECT id, question, answer, sources, confidence, latency_ms, created_at
                   FROM chat_messages ORDER BY created_at DESC LIMIT %s""",
                (limit,),
            )
            return await cur.fetchall()