async def create_document(db, filename, content_type, size, storage_path):
    cur = await db.execute(
        """
        INSERT INTO documents (filename, content_type, size, storage_path)
        VALUES (%s, %s, %s, %s)
        RETURNING id, filename, size, created_at
        """,
        (filename, content_type, size, storage_path),
    )
    return await cur.fetchone()

async def list_documents(db):
    cur = await db.execute(
        "SELECT id, filename, size, created_at FROM documents ORDER BY created_at DESC"
    )
    return await cur.fetchall()

async def get_document(db, doc_id: int):
    cur = await db.execute(
        "SELECT id, filename, content_type, storage_path FROM documents WHERE id = %s",
        (doc_id,),
    )
    return await cur.fetchone()

async def delete_document(db, doc_id: int):
    cur = await db.execute(
        "DELETE FROM documents WHERE id = %s RETURNING storage_path", (doc_id,)
    )
    return await cur.fetchone()