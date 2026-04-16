import asyncio
import os
import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List

import asyncpg
import redis.asyncio as aioredis
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("tweet-service")

app = FastAPI(title="Tweet Service")
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

DB_URL              = _build_db_url()
JWT_SECRET          = os.getenv("JWT_SECRET", "supersecretjwtkey")
REDIS_ADDR          = os.getenv("REDIS_ADDR", "redis:6379")
USE_REDIS           = os.getenv("USE_REDIS", "true").lower() == "true"
CONSISTENCY_MODE    = os.getenv("CONSISTENCY_MODE", "eventual")   # "strong" or "eventual"
FANOUT_WORKERS      = int(os.getenv("FANOUT_WORKER_COUNT", "5"))
FANOUT_QUEUE_SIZE   = int(os.getenv("FANOUT_CHAN_BUFFER", "10000"))
AGGREGATOR_INTERVAL = int(os.getenv("AGGREGATOR_INTERVAL_SECS", "30"))
FANOUT_PAGE_SIZE    = 500
TIMELINE_MAX_LEN    = 1000
TIMELINE_TTL_SECS   = 86400   # 24 h
ALGORITHM           = "HS256"

# ── Global state ──────────────────────────────────────────────────────────────
pool:         asyncpg.Pool      = None
rdb:          aioredis.Redis    = None
fanout_queue: asyncio.Queue     = None
security = HTTPBearer(auto_error=False)

# ── Startup / shutdown ────────────────────────────────────────────────────────
@app.on_event("startup")
async def startup():
    global pool, rdb, fanout_queue
    pool = await asyncpg.create_pool(DB_URL, min_size=2, max_size=10)

    host, port = REDIS_ADDR.split(":")
    rdb = aioredis.Redis(host=host, port=int(port), decode_responses=True)

    fanout_queue = asyncio.Queue(maxsize=FANOUT_QUEUE_SIZE)

    if USE_REDIS:
        for _ in range(FANOUT_WORKERS):
            asyncio.create_task(_fanout_worker())
        asyncio.create_task(_like_aggregator())

    logger.info("tweet service started (use_redis=%s, consistency=%s)", USE_REDIS, CONSISTENCY_MODE)

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

# ── Serialisation helper ──────────────────────────────────────────────────────
def _row(r) -> dict:
    d = dict(r)
    d["id"]         = str(d["id"])
    d["user_id"]    = str(d["user_id"])
    d["created_at"] = d["created_at"].isoformat()
    if d.get("reply_to_id"):
        d["reply_to_id"] = str(d["reply_to_id"])
    # username is present when fetched via batch (JOIN); absent on single-tweet endpoints
    d.setdefault("username", None)
    return d

# ── Fan-out worker ────────────────────────────────────────────────────────────
async def _fanout_worker():
    """Drain the fanout queue and push tweet IDs into follower Redis timelines."""
    while True:
        job = await fanout_queue.get()
        try:
            await _do_fanout(job["tweet_id"], job["author_id"])
        except Exception as e:
            logger.error("fanout error tweet=%s: %s", job["tweet_id"], e)
        finally:
            fanout_queue.task_done()

async def _do_fanout(tweet_id: str, author_id: str):
    """Paginate through followers and push tweet_id to each one's Redis timeline.
    Also pushes to the author's own timeline so their feed shows their own tweets."""
    # Push to the author's own timeline first
    pipe = rdb.pipeline()
    own_key = f"timeline:{author_id}"
    pipe.lpush(own_key, tweet_id)
    pipe.ltrim(own_key, 0, TIMELINE_MAX_LEN - 1)
    pipe.expire(own_key, TIMELINE_TTL_SECS)
    await pipe.execute()

    # Then paginate through followers
    after_id = None
    while True:
        async with pool.acquire() as conn:
            if after_id:
                rows = await conn.fetch(
                    """SELECT follower_id FROM follows
                       WHERE followee_id=$1 AND follower_id > $2
                       ORDER BY follower_id LIMIT $3""",
                    uuid.UUID(author_id), uuid.UUID(after_id), FANOUT_PAGE_SIZE,
                )
            else:
                rows = await conn.fetch(
                    "SELECT follower_id FROM follows WHERE followee_id=$1 ORDER BY follower_id LIMIT $2",
                    uuid.UUID(author_id), FANOUT_PAGE_SIZE,
                )

        if not rows:
            break

        pipe = rdb.pipeline()
        for row in rows:
            key = f"timeline:{row['follower_id']}"
            pipe.lpush(key, tweet_id)
            pipe.ltrim(key, 0, TIMELINE_MAX_LEN - 1)
            pipe.expire(key, TIMELINE_TTL_SECS)
        await pipe.execute()

        if len(rows) < FANOUT_PAGE_SIZE:
            break
        after_id = str(rows[-1]["follower_id"])

def _enqueue_fanout(tweet_id: str, author_id: str):
    try:
        fanout_queue.put_nowait({"tweet_id": tweet_id, "author_id": author_id})
    except asyncio.QueueFull:
        logger.warning("fanout queue full, dropping job tweet=%s", tweet_id)

# ── Like aggregator ───────────────────────────────────────────────────────────
async def _like_aggregator():
    """Periodically flush Redis like-count increments to PostgreSQL."""
    while True:
        await asyncio.sleep(AGGREGATOR_INTERVAL)
        try:
            await _flush_likes()
        except Exception as e:
            logger.error("like aggregator error: %s", e)

async def _flush_likes():
    """Read and delete all like_count_pending rows, then apply deltas to tweets."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT tweet_id, SUM(delta) AS total
               FROM like_count_pending
               WHERE created_at < NOW()
               GROUP BY tweet_id"""
        )
        if not rows:
            return
        await conn.execute("DELETE FROM like_count_pending WHERE created_at < NOW()")
        for row in rows:
            await conn.execute(
                "UPDATE tweets SET like_count = GREATEST(like_count + $1, 0) WHERE id = $2",
                int(row["total"]), row["tweet_id"],
            )
    # Drain Redis pending counters by the amount just flushed to DB.
    # This prevents _merge_like_counts from double-counting on the next read.
    try:
        pipe = rdb.pipeline()
        for row in rows:
            total = int(row["total"])
            if total != 0:
                pipe.incrby(f"like_count:{row['tweet_id']}", -total)
        await pipe.execute()
    except Exception as e:
        logger.warning("failed to drain Redis like counters after flush: %s", e)
    logger.info("flushed like counts for %d tweets", len(rows))

# ── Like count merge helper ───────────────────────────────────────────────────
async def _merge_like_counts(tweets: list[dict]) -> list[dict]:
    """
    In eventual-consistency mode the DB like_count lags behind by up to
    AGGREGATOR_INTERVAL seconds.  Merge the pending Redis delta so callers
    always see the up-to-date count.
    """
    if not USE_REDIS or not tweets:
        return tweets
    keys = [f"like_count:{t['id']}" for t in tweets]
    try:
        values = await rdb.mget(*keys)
        for tweet, val in zip(tweets, values):
            if val:
                tweet["like_count"] = max(0, tweet["like_count"] + int(val))
    except Exception as e:
        logger.warning("redis mget like_count failed: %s", e)
    return tweets

# ── Request models ────────────────────────────────────────────────────────────
class CreateTweetRequest(BaseModel):
    content: str
    reply_to_id: Optional[str] = None

class BatchRequest(BaseModel):
    ids: List[str]
    viewer_id: Optional[str] = None

# ── Endpoints ─────────────────────────────────────────────────────────────────

# NOTE: /v1/tweets/batch must come BEFORE /v1/tweets/{id} so FastAPI doesn't
# treat "batch" as a tweet ID.
@app.post("/v1/tweets/batch")
async def get_batch(req: BatchRequest):
    """Internal endpoint: bulk-fetch tweets by ID list (used by timeline service)."""
    if not req.ids:
        return []
    uuids = [uuid.UUID(i) for i in req.ids]
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT t.id, t.user_id, t.content, t.like_count, t.reply_to_id, t.created_at,
                      u.username
               FROM tweets t
               JOIN users u ON u.id = t.user_id
               WHERE t.id = ANY($1)
               ORDER BY t.created_at DESC""",
            uuids,
        )
    tweets = [_row(r) for r in rows]
    tweets = await _merge_like_counts(tweets)

    # Annotate liked_by_me when a viewer is identified
    if req.viewer_id and tweets:
        vid = uuid.UUID(req.viewer_id)
        tid_list = [uuid.UUID(t["id"]) for t in tweets]
        async with pool.acquire() as conn:
            liked_rows = await conn.fetch(
                "SELECT tweet_id FROM likes WHERE user_id=$1 AND tweet_id=ANY($2)",
                vid, tid_list,
            )
        liked_set = {str(r["tweet_id"]) for r in liked_rows}
        for t in tweets:
            t["liked_by_me"] = t["id"] in liked_set
    else:
        for t in tweets:
            t["liked_by_me"] = False

    return tweets


@app.post("/v1/tweets", status_code=201)
async def create_tweet(req: CreateTweetRequest, me: dict = Depends(_current_user)):
    if not req.content or len(req.content) > 280:
        raise HTTPException(400, "content must be 1-280 characters")
    reply_id = uuid.UUID(req.reply_to_id) if req.reply_to_id else None
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """INSERT INTO tweets (user_id, content, reply_to_id)
               VALUES ($1, $2, $3)
               RETURNING id, user_id, content, like_count, reply_to_id, created_at""",
            uuid.UUID(me["user_id"]), req.content, reply_id,
        )
    tweet = _row(row)
    if USE_REDIS:
        _enqueue_fanout(tweet["id"], tweet["user_id"])
    return tweet


@app.get("/v1/tweets/{tweet_id}")
async def get_tweet(tweet_id: str):
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, user_id, content, like_count, reply_to_id, created_at FROM tweets WHERE id=$1",
            uuid.UUID(tweet_id),
        )
    if not row:
        raise HTTPException(404, "tweet not found")
    tweets = await _merge_like_counts([_row(row)])
    return tweets[0]


@app.delete("/v1/tweets/{tweet_id}", status_code=204)
async def delete_tweet(tweet_id: str, me: dict = Depends(_current_user)):
    async with pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM tweets WHERE id=$1 AND user_id=$2",
            uuid.UUID(tweet_id), uuid.UUID(me["user_id"]),
        )
    if result == "DELETE 0":
        raise HTTPException(404, "tweet not found or not yours")


@app.post("/v1/tweets/{tweet_id}/like", status_code=204)
async def like_tweet(tweet_id: str, me: dict = Depends(_current_user)):
    tid = uuid.UUID(tweet_id)
    uid = uuid.UUID(me["user_id"])
    async with pool.acquire() as conn:
        result = await conn.execute(
            "INSERT INTO likes (user_id, tweet_id) VALUES ($1,$2) ON CONFLICT DO NOTHING",
            uid, tid,
        )
    # "INSERT 0 0" means ON CONFLICT triggered — already liked, skip counter update
    if result == "INSERT 0 0":
        return
    if CONSISTENCY_MODE == "strong":
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE tweets SET like_count = like_count + 1 WHERE id=$1", tid,
            )
    else:
        # Eventual: increment Redis counter + durable fallback row
        await rdb.incr(f"like_count:{tweet_id}")
        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO like_count_pending (tweet_id, delta) VALUES ($1, 1)", tid,
            )


@app.delete("/v1/tweets/{tweet_id}/like", status_code=204)
async def unlike_tweet(tweet_id: str, me: dict = Depends(_current_user)):
    tid = uuid.UUID(tweet_id)
    uid = uuid.UUID(me["user_id"])
    async with pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM likes WHERE user_id=$1 AND tweet_id=$2", uid, tid,
        )
    # "DELETE 0" means row didn't exist — already unliked, skip counter update
    if result == "DELETE 0":
        return
    if CONSISTENCY_MODE == "strong":
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE tweets SET like_count = GREATEST(like_count-1,0) WHERE id=$1", tid,
            )
    else:
        await rdb.decr(f"like_count:{tweet_id}")
        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO like_count_pending (tweet_id, delta) VALUES ($1, -1)", tid,
            )


@app.get("/health")
async def health():
    return {"status": "ok"}
