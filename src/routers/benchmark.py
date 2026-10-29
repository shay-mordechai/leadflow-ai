# src/routers/benchmark.py
from fastapi import APIRouter, Request, Response

router = APIRouter(prefix="/bench", tags=["Benchmarking"])


@router.post("/echo")
async def bench_echo(request: Request, response: Response):
    # Set a custom header to indicate the data's time-to-live (TTL)
    response.headers["X-Data-TTL"] = "1"
    body = await request.json()
    return body

from fastapi import Request

@router.post("/log")
async def bench_log(request: Request):
    raw_body = (await request.body()).decode()
    print(f"BACKEND GOT: {raw_body}", flush=True)
    return {"status": "received", "data": raw_body}

@router.get("/fixed")
async def bench_fixed():
    return {"phone": "052-123-4567", "email": "dana@example.com"}