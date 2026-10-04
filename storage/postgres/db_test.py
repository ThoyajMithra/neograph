from database import create_pool, init_db
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel

import pandas as pd


class DocumentOut(BaseModel):
    id: UUID
    name: str
    checksum: str
    created_at: datetime
    char_count: int

class Files(BaseModel):
    document_id: UUID


def list_documents(pool):
    with pool.connection() as conn:
        cur = conn.execute(
            """SELECT document_id from chunks"""
        )
        rows = cur.fetchall()
        for i in rows:
            print(i)
        return [Files(**i) for i in rows]

def delet(pool):
    with pool.connection() as conn:
        cur = conn.execute(
            "DROP TABLE documents"
        )
        # rows = cur.fetchall()
        # for i in rows:
        #     print(i)
        # return [Files(**i) for i in rows]
if __name__ == "__main__":
    pool = create_pool()
    init_db(pool)

    docs = list_documents(pool)
    # delet(pool)
    # print(docs)