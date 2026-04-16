import asyncio
import os
import uuid
import logging
from typing import Optional, List

import asyncpg
import httpx
import redis.asyncio as aioredis
from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("timeline-service")

app = FastAPI(title="Timeline Service")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ── Config ────────────────────────────────────────────────────────────────────
def _build_db_url() -> str:
    url = os.getenv("POSTGRES_PRIMARY_URL")
    if url:
        return url
    host = os.getenv("DB_HOST", "postgres-primary")
    port = os.getenv("DB_PORT", "5432")
    user = os.getenv("DB_USER", "twitter")
    pwd  = os.getenv("DB_PASSWORD", "twitter")
    name = os.getenv("DB_NAME", "twitter")
    return f"postgresql://{user}:{pwd}@{host}:{port}/{name}"

DB_URL            = _build_db_url()
JWT_SECRET        = os.getenv("JWT_SECRET", "supersecretjwtkey")
REDIS_ADDR        = os.getenv("REDIS_ADDR", "redis:6379")
TWEET_SERVICE_URL = os.getenv("TWEET_SERVICE_URL", "http://tweet-service:8082")
USE_REDIS         = os.getenv("USE_REDIS", "true").lower() == "true"
ALGORITHM         = "HS256"
DEFAULT_LIMIT     = 50
TIMELINE_MAX_LEN  = 1000

# ── Global state ──────────────────────────────────────────────────────────────
pool:     asyncpg.Pool   = None
rdb:      aioredis.Redis = None
security = HTTPBearer(auto_error=False)

@app.on_event("startup")
async def startup():
    global pool, rdb
    pool = await asyncpg.create_pool(DB_URL, min_size=2, max_size=10)
    host, port = REDIS_ADDR.split(":")
    rdb = aioredis.Redis(host=host, port=int(port), decode_responses=True)
    logger.info("timeline service started (use_redis=%s)", USE_REDIS)

@app.on_event("shutdown")
async def shutdown():
    if pool:
        await pool.close()
    if rdb:
        await rdb.aclose()

# ── JWT auth ──────────────────────────────────────────────────────────────────
def _current_user(creds: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    if creds is None:
        raise HTTPException(401, "unauthorized")
    try:
        payload = jwt.decode(creds.credentials, JWT_SECRET, algorithms=[ALGORITHM])
        return {"user_id": payload["user_id"]}
    except JWTError:
        raise HTTPException(401, "invalid token")

# ── Redis helpers ─────────────────────────────────────────────────────────────
TIMELINE_TTL_SECS = 86400  # 24 h (must match tweet service)
TIMELINE_MAX_LEN  = 1000   # must match tweet service

async def _get_cached_ids(user_id: str, limit: int) -> Optional[List[str]]:
    """Return tweet-ID strings from Redis, or None on miss."""
    try:
        ids = await rdb.lrange(f"timeline:{user_id}", 0, limit - 1)
        return ids if ids else None
    except Exception as e:
        logger.warning("redis lrange failed: %s", e)
        return None

async def _write_back_cache(user_id: str, ids: List[str]):
    """Populate Redis timeline cache from DB results (newest-first list)."""
    if not ids:
        return
    try:
        key = f"timeline:{user_id}"
        pipe = rdb.pipeline()
        pipe.delete(key)
        # ids are newest-first from DB; RPUSH preserves that order in the list
        pipe.rpush(key, *ids)
        pipe.ltrim(key, 0, TIMELINE_MAX_LEN - 1)
        pipe.expire(key, TIMELINE_TTL_SECS)
        await pipe.execute()
    except Exception as e:
        logger.warning("cache write-back failed for user %s: %s", user_id, e)

# ── DB helpers ────────────────────────────────────────────────────────────────
async def _followee_ids(user_id: str) -> List[uuid.UUID]:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT followee_id FROM follows WHERE follower_id=$1", uuid.UUID(user_id),
        )
    return [r["followee_id"] for r in rows]

async def _db_home_ids(followee_ids: List[uuid.UUID], limit: int, before_ns: Optional[int]) -> List[str]:
    if not followee_ids:
        return []
    async with pool.acquire() as conn:
        if before_ns:
            from datetime import datetime, timezone
            before_dt = datetime.fromtimestamp(before_ns / 1e9, tz=timezone.utc)
            rows = await conn.fetch(
                """SELECT id FROM tweets
                   WHERE user_id = ANY($1) AND created_at < $2
                   ORDER BY created_at DESC LIMIT $3""",
                followee_ids, before_dt, limit,
            )
        else:
            rows = await conn.fetch(
                """SELECT id FROM tweets
                   WHERE user_id = ANY($1)
                   ORDER BY created_at DESC LIMIT $2""",
                followee_ids, limit,
            )
    return [str(r["id"]) for r in rows]

async def _db_user_ids(user_id: str, limit: int, before_ns: Optional[int]) -> List[str]:
    async with pool.acquire() as conn:
        if before_ns:
            from datetime import datetime, timezone
            before_dt = datetime.fromtimestamp(before_ns / 1e9, tz=timezone.utc)
            rows = await conn.fetch(
                """SELECT id FROM tweets
                   WHERE user_id=$1 AND created_at < $2
                   ORDER BY created_at DESC LIMIT $3""",
                uuid.UUID(user_id), before_dt, limit,
            )
        else:
            rows = await conn.fetch(
                """SELECT id FROM tweets
                   WHERE user_id=$1
                   ORDER BY created_at DESC LIMIT $2""",
                uuid.UUID(user_id), limit,
            )
    return [str(r["id"]) for r in rows]

# ── Tweet enrichment (calls tweet service batch endpoint) ─────────────────────
async def _enrich(ids: List[str], viewer_id: Optional[str] = None) -> List[dict]:
    """Hydrate tweet IDs into full tweet objects via the tweet service."""
    if not ids:
        return []
    body = {"ids": ids}
    if viewer_id:
        body["viewer_id"] = viewer_id
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            f"{TWEET_SERVICE_URL}/v1/tweets/batch",
            json=body,
        )
        resp.raise_for_status()
        return resp.json()

# ── Endpoints ─────────────────────────────────────────────────────────────────
@app.get("/v1/timeline/home")
async def home_timeline(
    limit:     int            = Query(DEFAULT_LIMIT, ge=1, le=100),
    before:    Optional[int]  = Query(None, description="Unix nanosecond cursor"),
    me:        dict           = Depends(_current_user),
):
    user_id = me["user_id"]
    clamp   = min(limit, DEFAULT_LIMIT)

    if USE_REDIS:
        # Fan-out-on-write: read pre-built timeline from Redis
        cached_ids = await _get_cached_ids(user_id, clamp)
        if cached_ids:
            tweets = await _enrich(cached_ids, viewer_id=user_id)
            return {"tweets": tweets}
        # Cache miss → fall back to DB
        logger.info("timeline cache miss for user %s", user_id)

    followee_ids = await _followee_ids(user_id)
    # Include the user's own tweets in their home feed
    all_ids = list({*followee_ids, uuid.UUID(user_id)})
    ids     = await _db_home_ids(all_ids, clamp, before)
    tweets  = await _enrich(ids, viewer_id=user_id)

    # Populate Redis cache so the next read (e.g. after a fanout) has full history
    if USE_REDIS and ids and not before:
        asyncio.create_task(_write_back_cache(user_id, ids))

    return {"tweets": tweets}


@app.get("/v1/timeline/user/{user_id}")
async def user_timeline(
    user_id: str,
    limit:   int           = Query(DEFAULT_LIMIT, ge=1, le=100),
    before:  Optional[int] = Query(None, description="Unix nanosecond cursor"),
):
    clamp = min(limit, DEFAULT_LIMIT)
    ids   = await _db_user_ids(user_id, clamp, before)
    tweets = await _enrich(ids)
    return {"tweets": tweets}


@app.get("/health")
async def health():
    return {"status": "ok"}
