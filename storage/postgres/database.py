from pathlib import Path

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

import os
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

def create_pool() -> ConnectionPool:
    """A pool keeps a few connections open and reuses them, so each
    request doesn't have to open a new one."""
    pool = ConnectionPool(
        conninfo=DATABASE_URL,
        min_size=1,
        max_size=5,
        open=False,
        kwargs={"row_factory": dict_row},  # rows come back as dicts
    )
    pool.open()
    return pool


def init_db(pool: ConnectionPool) -> None:
    """Run schema.sql once at startup."""
    sql = (Path(__file__).parent / "schema.sql").read_text()
    with pool.connection() as conn:
        conn.execute(sql)