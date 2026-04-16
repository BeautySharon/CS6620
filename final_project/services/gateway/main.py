import os
import time
import logging

import httpx
import redis.asyncio as aioredis
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("gateway")

app = FastAPI(title="API Gateway")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Config ────────────────────────────────────────────────────────────────────
USER_SERVICE_URL     = os.getenv("USER_SERVICE_URL",     "http://user-service:8081")
TWEET_SERVICE_URL    = os.getenv("TWEET_SERVICE_URL",    "http://tweet-service:8082")
TIMELINE_SERVICE_URL = os.getenv("TIMELINE_SERVICE_URL", "http://timeline-service:8083")
RATE_LIMIT_RPM       = int(os.getenv("RATE_LIMIT_RPM", "5000"))
REDIS_ADDR           = os.getenv("REDIS_ADDR", "redis:6379")

# ── Redis client ──────────────────────────────────────────────────────────────
rdb: aioredis.Redis = None

@app.on_event("startup")
async def startup():
    global rdb
    host, port = REDIS_ADDR.split(":")
    rdb = aioredis.Redis(host=host, port=int(port), decode_responses=True)

@app.on_event("shutdown")
async def shutdown():
    if rdb:
        await rdb.aclose()

# ── Rate limiting ─────────────────────────────────────────────────────────────
def _real_ip(request: Request) -> str:
    if ip := request.headers.get("x-real-ip"):
        return ip
    if ip := request.headers.get("x-forwarded-for"):
        return ip.split(",")[0].strip()
    return request.client.host if request.client else "unknown"

async def _check_rate_limit(request: Request) -> tuple[bool, int]:
    """Returns (allowed, current_count). Fails open on Redis errors."""
    if rdb is None:
        return True, 0
    ip     = _real_ip(request)
    minute = int(time.time()) // 60
    key    = f"rate_limit:{ip}:{minute}"
    try:
        pipe    = rdb.pipeline()
        pipe.incr(key)
        pipe.expire(key, 61)
        results = await pipe.execute()
        count   = int(results[0])
        return count <= RATE_LIMIT_RPM, count
    except Exception as e:
        logger.warning("rate limit redis error: %s", e)
        return True, 0

# ── Routing table ─────────────────────────────────────────────────────────────
def _target(path: str) -> str | None:
    """Map an incoming /v1/... path to the correct downstream base URL."""
    if path.startswith("/v1/auth/") or path.startswith("/v1/users/") or path == "/v1/users":
        return USER_SERVICE_URL
    if path.startswith("/v1/tweets/") or path == "/v1/tweets":
        return TWEET_SERVICE_URL
    if path.startswith("/v1/timeline/"):
        return TIMELINE_SERVICE_URL
    return None

# ── Hop-by-hop headers to strip before forwarding ────────────────────────────
_HOP_BY_HOP = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailers", "transfer-encoding", "upgrade", "host",
    "content-length",   # httpx sets its own
}

async def _proxy(request: Request, base_url: str) -> Response:
    """Forward the request to base_url, preserving method/headers/body."""
    url  = base_url + request.url.path
    if request.url.query:
        url += "?" + request.url.query

    body = await request.body()
    headers = {k: v for k, v in request.headers.items()
               if k.lower() not in _HOP_BY_HOP}

    async with httpx.AsyncClient(timeout=30.0) as client:
        upstream = await client.request(
            method=request.method,
            url=url,
            content=body,
            headers=headers,
        )

    # Strip hop-by-hop from upstream response too
    resp_headers = {k: v for k, v in upstream.headers.items()
                    if k.lower() not in _HOP_BY_HOP}
    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        headers=resp_headers,
        media_type=upstream.headers.get("content-type"),
    )

# ── Catch-all proxy route ─────────────────────────────────────────────────────
@app.api_route("/v1/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def gateway(request: Request, path: str):
    full_path = f"/v1/{path}"

    allowed, count = await _check_rate_limit(request)
    if not allowed:
        return Response(
            content='{"error":"rate limit exceeded"}',
            status_code=429,
            media_type="application/json",
            headers={
                "X-RateLimit-Limit":     str(RATE_LIMIT_RPM),
                "X-RateLimit-Remaining": "0",
            },
        )

    target = _target(full_path)
    if target is None:
        return Response(
            content='{"error":"not found"}',
            status_code=404,
            media_type="application/json",
        )

    return await _proxy(request, target)

@app.get("/health")
async def health():
    return {"status": "ok"}
