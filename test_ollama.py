import asyncio
import time
import httpx
from engine.client_async import get_async_ollama_client


async def main():
    print("1. Python started", flush=True)

    client = get_async_ollama_client()
    print("2. Client created", flush=True)

    try:
        print("3. Sending request to Ollama...", flush=True)
        start = time.perf_counter()

        response = await client.chat.completions.create(
            model="qwen3:4b",
            messages=[
                {"role": "user", "content": "Reply with exactly: HELLO"}
            ],
            stream=False,
            timeout=httpx.Timeout(180.0, connect=5.0),
            extra_body={
                "think": False,
                "options": {"num_predict": 20}
            }
        )

        print("4. Response received!", flush=True)
        print(response.choices[0].message.content, flush=True)
        print(f"Time: {time.perf_counter() - start:.2f}s", flush=True)

    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}", flush=True)

    finally:
        await client.close()
        print("5. Client closed", flush=True)


if __name__ == "__main__":
    asyncio.run(main())