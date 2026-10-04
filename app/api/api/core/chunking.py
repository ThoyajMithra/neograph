def save_document_with_chunks(pool, name: str, content: str, checksum: str,chunks: list[tuple[str | None, str]]) -> dict:
    with pool.connection() as conn:   # one transaction: doc and chunks both save, or neither
        cur = conn.execute(
            """INSERT INTO documents (name, content, checksum)
               VALUES (%s, %s, %s)
               RETURNING id, name, checksum, created_at, length(content) AS char_count""",
            (name, content, checksum),
        )
        doc = cur.fetchone()

        with conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO chunks (document_id, idx, heading, text) VALUES (%s, %s, %s, %s)",
                [(doc["id"], i, heading, text) for i, (heading, text) in enumerate(chunks)],
            )
        doc["chunk_count"] = len(chunks)
        return doc


def get_chunks(pool, doc_id) -> list[dict]:
    with pool.connection() as conn:
        cur = conn.execute(
            """SELECT id, document_id, idx, heading, text
               FROM chunks WHERE document_id = %s ORDER BY idx""",
            (doc_id,),
        )
        return cur.fetchall()