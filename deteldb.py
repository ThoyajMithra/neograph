import asyncio
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(
        asyncio.WindowsSelectorEventLoopPolicy()
    )

from storage.database import create_pool


async def delete_tables(pool):
    async with pool.connection() as conn:
        await conn.execute("""
            DROP TABLE IF EXISTS
                documents,
                chunks,
                chat_messages,
                nodes,
                edges
            CASCADE
        """)
        await conn.commit()

    print("Tables deleted successfully.")


async def main():
    pool = await create_pool()
    try:
        await delete_tables(pool)
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
