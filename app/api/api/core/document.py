def insert_document(pool, name: str, content: str, checksum: str) -> dict:
    with pool.connection() as conn:
        cur = conn.execute(
            """INSERT INTO documents (name, content, checksum)
               VALUES (%s, %s, %s)
               RETURNING id, name, checksum, created_at, length(content) AS char_count""",
            (name, content, checksum),
        )
        return cur.fetchone()


def get_by_checksum(pool, checksum: str) -> dict | None:
    with pool.connection() as conn:
        cur = conn.execute(
            """SELECT id, name, checksum, created_at, length(content) AS char_count
               FROM documents WHERE checksum = %s""",
            (checksum,),
        )
        return cur.fetchone()


def list_documents(pool) -> list[dict]:
    with pool.connection() as conn:
        cur = conn.execute(
            """SELECT id, name, checksum, created_at, length(content) AS char_count
               FROM documents ORDER BY created_at DESC"""
        )
        return cur.fetchall()


def get_document(pool, doc_id) -> dict | None:
    with pool.connection() as conn:
        cur = conn.execute(
            "SELECT id, name, content, checksum, created_at FROM documents WHERE id = %s",
            (doc_id,),
        )
        return cur.fetchone()


def delete_document(pool, doc_id) -> bool:
    with pool.connection() as conn:
        cur = conn.execute("DELETE FROM documents WHERE id = %s", (doc_id,))
        return cur.rowcount > 0