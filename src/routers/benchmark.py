# src/routers/benchmark.py
from fastapi import APIRouter, Request, Response

router = APIRouter(prefix="/bench", tags=["Benchmarking"])


@router.post("/echo")
async def bench_echo(request: Request, response: Response):
    # Set a custom header to indicate the data's time-to-live (TTL)
    response.headers["X-Data-TTL"] = "1"
    body = await request.json()
    return body
