from pathlib import Path

from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

import os
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

async def create_pool() -> AsyncConnectionPool:
    pool = AsyncConnectionPool(
        conninfo=DATABASE_URL,
        min_size=1,
        max_size=10,
        open=False,
        kwargs={"row_factory": dict_row},
    )
    await pool.open()
    return pool


async def init_db(pool: AsyncConnectionPool) -> None:
    sql = (Path(__file__).parent / "schema.sql").read_text()
    async with pool.connection() as conn:
        await conn.execute(sql)