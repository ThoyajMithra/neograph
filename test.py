from engine.embedding.encoder import LocalEncoder

# Test Data
sample_text = "How is the weather today?"
sample_list = ["Machine learning is fascinating.", "Python is a great language."]

print("--- 1. Testing LocalEncoder ---")
local_encoder = LocalEncoder()

# Test single string encoding
single_local_embedding = local_encoder.encode_single(sample_text)
print(f"Single text embedding shape: ({len(single_local_embedding)},)")
print(f"Sample values: {single_local_embedding[:3]}...")

# Test batch list encoding
batch_local_embeddings = local_encoder.encode(sample_list)
print(f"Batch text embedding shape: ({len(batch_local_embeddings)}, {len(batch_local_embeddings[0])})\n")

# import asyncio
# import sys

# if sys.platform == "win32":
#     asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


# import asyncio

# from storage.database import init_db, create_pool

# async def que(pool):
#     async with pool.connection() as conn:
#         cur = await conn.execute(
#             "DROP TABLE documents"
#         )
#         a = await cur.fetchall()
#         for i in a:
#             print(i)

# async def main():
#     pool = await create_pool()
#     await init_db(pool)
#     await que(pool)

# asyncio.run(main())
