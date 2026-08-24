# bench.py
# Fires REQUESTS requests in parallel at each /sleep-* endpoint and prints the
# wall-clock time. Needs a running server: fastapi dev main.py
# Run with: python bench.py
import asyncio
import time

import httpx

BASE_URL = "http://127.0.0.1:8000"
REQUESTS = 10
SECONDS = 1.0

ENDPOINTS = [
    ("/sleep-blocking", "async def + time.sleep    (blocks the loop)"),
    ("/sleep-async", "async def + asyncio.sleep (correct)"),
    ("/sleep-threaded", "def + time.sleep          (threadpool)"),
]


async def measure(client: httpx.AsyncClient, path: str) -> float:
    start = time.perf_counter()
    await asyncio.gather(
        *(client.get(path, params={"seconds": SECONDS}) for _ in range(REQUESTS))
    )
    return time.perf_counter() - start


async def main():
    print(f"{REQUESTS} parallel requests, {SECONDS}s sleep each")
    print(f"Ideal result: ~{SECONDS}s. Serialized: ~{REQUESTS * SECONDS:.0f}s\n")

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=120) as client:
        for path, label in ENDPOINTS:
            elapsed = await measure(client, path)
            print(f"{label:44} {elapsed:5.1f}s")


if __name__ == "__main__":
    asyncio.run(main())
