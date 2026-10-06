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

    async def list_turns(self, limit: int = 50) -> list[dict]:
        async with self.pool.connection() as conn:
            cur = await conn.execute(
                """SELECT id, question, answer, sources, confidence, latency_ms, created_at
                   FROM chat_messages ORDER BY created_at DESC LIMIT %s""",
                (limit,),
            )
            return await cur.fetchall()