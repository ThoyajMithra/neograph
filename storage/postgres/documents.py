class PostgresStore:
    def __init__(self, pool):
        self.pool = pool

    async def get_by_checksum(self, checksum: str) -> dict | None:
        async with self.pool.connection() as conn:
            cur = await conn.execute(
                "SELECT id, name FROM documents WHERE checksum = %s", (checksum,)
            )
            return await cur.fetchone()

    async def list_documents(self) -> list[dict]:
        async with self.pool.connection() as conn:
            cur = await conn.execute(
                """SELECT id, name, checksum, created_at, length(content) AS char_count
                   FROM documents ORDER BY created_at DESC"""
            )
            return await cur.fetchall()

    async def get_document(self, doc_id) -> dict | None:
        async with self.pool.connection() as conn:
            cur = await conn.execute(
                """SELECT id, name, content, checksum, created_at,
                          length(content) AS char_count
                   FROM documents WHERE id = %s""",
                (doc_id,),
            )
            return await cur.fetchone()

    async def delete_document(self, doc_id) -> bool:
        async with self.pool.connection() as conn:
            cur = await conn.execute("DELETE FROM documents WHERE id = %s", (doc_id,))
            return cur.rowcount > 0

    async def save_document_with_chunks(self, name: str, content: str, checksum: str,
                                        chunks: list[tuple[str | None, str]],
                                        embeddings: list[list[float]]) -> dict:
        """One connection = one transaction: document and chunks save together, or neither."""
        async with self.pool.connection() as conn:
            cur = await conn.execute(
                """INSERT INTO documents (name, content, checksum)
                   VALUES (%s, %s, %s) RETURNING id, name""",
                (name, content, checksum),
            )
            doc = await cur.fetchone()

            async with conn.cursor() as cur:
                await cur.executemany(
                    """INSERT INTO chunks (document_id, idx, heading, text, embedding)
                       VALUES (%s, %s, %s, %s, %s::vector)""",
                    [
                        (doc["id"], i, h, t, str(emb))
                        for i, ((h, t), emb) in enumerate(zip(chunks, embeddings))
                    ],
                )
            doc["chunk_count"] = len(chunks)
            return doc

    async def get_chunks(self, doc_id) -> list[dict]:
        async with self.pool.connection() as conn:
            cur = await conn.execute(
                """SELECT id, document_id, idx, heading, text
                   FROM chunks WHERE document_id = %s ORDER BY idx""",
                (doc_id,),
            )
            return await cur.fetchall()

    async def get_chunk(self, chunk_id) -> dict | None:
        async with self.pool.connection() as conn:
            cur = await conn.execute(
                """SELECT id, document_id, idx, heading, text
                   FROM chunks WHERE id = %s::uuid""",
                (chunk_id,),
            )
            return await cur.fetchone()

