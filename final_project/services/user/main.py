import os
import uuid
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import asyncpg
import redis.asyncio as aioredis
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("user-service")

app = FastAPI(title="User Service")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ── Config ────────────────────────────────────────────────────────────────────
def _build_db_url() -> str:
    """Support both a full URL (local/docker) and individual ECS-injected components."""
    url = os.getenv("POSTGRES_PRIMARY_URL")
    if url:
        return url
    host = os.getenv("DB_HOST", "postgres-primary")
    port = os.getenv("DB_PORT", "5432")
    user = os.getenv("DB_USER", "twitter")
    pwd  = os.getenv("DB_PASSWORD", "twitter")
    name = os.getenv("DB_NAME", "twitter")
    return f"postgresql://{user}:{pwd}@{host}:{port}/{name}"

DB_URL          = _build_db_url()
JWT_SECRET      = os.getenv("JWT_SECRET", "supersecretjwtkey")
JWT_EXPIRY_HOURS = int(os.getenv("JWT_EXPIRY_HOURS", "24"))
REDIS_ADDR      = os.getenv("REDIS_ADDR", "redis:6379")
USE_REDIS       = os.getenv("USE_REDIS", "true").lower() == "true"
ALGORITHM       = "HS256"

# Schema migrations (idempotent — all use IF NOT EXISTS)
_MIGRATIONS = [
    # 001 users
    """
    CREATE TABLE IF NOT EXISTS users (
        id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        username        VARCHAR(50)  NOT NULL UNIQUE,
        email           VARCHAR(255) NOT NULL UNIQUE,
        password_hash   TEXT         NOT NULL,
        display_name    VARCHAR(100),
        bio             TEXT,
        follower_count  INT NOT NULL DEFAULT 0,
        following_count INT NOT NULL DEFAULT 0,
        created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
    """,
    # 002 tweets
    """
    CREATE TABLE IF NOT EXISTS tweets (
        id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        content     VARCHAR(280) NOT NULL,
        like_count  INT NOT NULL DEFAULT 0,
        reply_to_id UUID REFERENCES tweets(id) ON DELETE SET NULL,
        created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS idx_tweets_user_id_created ON tweets(user_id, created_at DESC);
    """,
    # 003 follows
    """
    CREATE TABLE IF NOT EXISTS follows (
        follower_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        followee_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        PRIMARY KEY (follower_id, followee_id)
    );
    CREATE INDEX IF NOT EXISTS idx_follows_followee ON follows(followee_id);
    """,
    # 004 likes + like_count_pending
    """
    CREATE TABLE IF NOT EXISTS likes (
        user_id    UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        tweet_id   UUID NOT NULL REFERENCES tweets(id) ON DELETE CASCADE,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        PRIMARY KEY (user_id, tweet_id)
    );
    CREATE INDEX IF NOT EXISTS idx_likes_tweet ON likes(tweet_id);

    CREATE TABLE IF NOT EXISTS like_count_pending (
        tweet_id   UUID NOT NULL REFERENCES tweets(id) ON DELETE CASCADE,
        delta      INT  NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    """,
]

# ── Crypto ────────────────────────────────────────────────────────────────────
def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def _verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())

security = HTTPBearer(auto_error=False)

# ── DB pool + Redis ───────────────────────────────────────────────────────────
pool: asyncpg.Pool   = None
rdb:  aioredis.Redis = None

@app.on_event("startup")
async def startup():
    global pool, rdb
    pool = await asyncpg.create_pool(DB_URL, min_size=2, max_size=10)
    host, port = REDIS_ADDR.split(":")
    rdb = aioredis.Redis(host=host, port=int(port), decode_responses=True)

    # Run schema migrations (all idempotent via IF NOT EXISTS — safe to re-run)
    async with pool.acquire() as conn:
        for i, sql in enumerate(_MIGRATIONS, start=1):
            try:
                await conn.execute(sql)
                logger.info("migration %03d applied", i)
            except Exception as e:
                logger.error("migration %03d failed: %s", i, e)
                raise

    # Recalculate all follow counts from the source-of-truth follows table,
    # healing any counters that were corrupted by previous double-follow bugs.
    async with pool.acquire() as conn:
        await conn.execute("""
            UPDATE users u
            SET following_count = (SELECT COUNT(*) FROM follows WHERE follower_id = u.id),
                follower_count  = (SELECT COUNT(*) FROM follows WHERE followee_id = u.id)
        """)

@app.on_event("shutdown")
async def shutdown():
    if pool:
        await pool.close()
    if rdb:
        await rdb.aclose()

# ── JWT helpers ───────────────────────────────────────────────────────────────
def _create_token(user_id: str, username: str) -> str:
    exp = datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRY_HOURS)
    return jwt.encode(
        {"user_id": user_id, "username": username, "exp": exp},
        JWT_SECRET, algorithm=ALGORITHM,
    )

def _current_user(creds: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    if creds is None:
        raise HTTPException(status_code=401, detail="unauthorized")
    try:
        payload = jwt.decode(creds.credentials, JWT_SECRET, algorithms=[ALGORITHM])
        return {"user_id": payload["user_id"], "username": payload["username"]}
    except JWTError:
        raise HTTPException(status_code=401, detail="invalid token")

# ── Serialisation helper ──────────────────────────────────────────────────────
def _row(record, include_email: bool = False) -> dict:
    d = dict(record)
    d["id"]         = str(d["id"])
    d["created_at"] = d["created_at"].isoformat()
    d.pop("password_hash", None)
    if not include_email:
        d.pop("email", None)
    return d

# ── Request models ────────────────────────────────────────────────────────────
class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str

class LoginRequest(BaseModel):
    username: str
    password: str

class UpdateProfileRequest(BaseModel):
    display_name: str = ""
    bio: str = ""

# ── Endpoints ─────────────────────────────────────────────────────────────────
@app.post("/v1/auth/register", status_code=201)
async def register(req: RegisterRequest):
    if not req.username or not req.email or not req.password:
        raise HTTPException(400, "username, email, and password are required")
    pw_hash = _hash_password(req.password)
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """INSERT INTO users (username, email, password_hash, display_name, bio)
                   VALUES ($1, $2, $3, '', '')
                   RETURNING id, username, email, password_hash, display_name, bio,
                             follower_count, following_count, created_at""",
                req.username, req.email, pw_hash,
            )
    except asyncpg.UniqueViolationError:
        raise HTTPException(409, "username or email already exists")
    user  = _row(row, include_email=True)
    token = _create_token(user["id"], user["username"])
    return {"user": user, "token": token}


@app.post("/v1/auth/login")
async def login(req: LoginRequest):
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """SELECT id, username, email, password_hash, display_name, bio,
                      follower_count, following_count, created_at
               FROM users WHERE username = $1""",
            req.username,
        )
    if not row or not _verify_password(req.password, row["password_hash"]):
        raise HTTPException(401, "invalid credentials")
    user  = _row(row, include_email=True)
    token = _create_token(user["id"], user["username"])
    return {"user": user, "token": token}


@app.get("/v1/users/me")
async def get_me(me: dict = Depends(_current_user)):
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """SELECT id, username, email, display_name, bio,
                      follower_count, following_count, created_at
               FROM users WHERE id = $1""",
            uuid.UUID(me["user_id"]),
        )
    if not row:
        raise HTTPException(404, "user not found")
    return _row(row, include_email=True)


@app.get("/v1/users/{username}")
async def get_user(username: str, creds: HTTPAuthorizationCredentials = Depends(security)):
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """SELECT id, username, display_name, bio,
                      follower_count, following_count, created_at
               FROM users WHERE username = $1""",
            username,
        )
    if not row:
        raise HTTPException(404, "user not found")
    result = _row(row)

    # If caller is authenticated, tell them whether they already follow this user
    result["you_follow"] = False
    if creds:
        try:
            payload = jwt.decode(creds.credentials, JWT_SECRET, algorithms=[ALGORITHM])
            viewer_id = uuid.UUID(payload["user_id"])
            async with pool.acquire() as conn:
                follow_row = await conn.fetchrow(
                    "SELECT 1 FROM follows WHERE follower_id=$1 AND followee_id=$2",
                    viewer_id, uuid.UUID(result["id"]),
                )
            result["you_follow"] = follow_row is not None
        except JWTError:
            pass

    return result


@app.put("/v1/users/me")
async def update_me(req: UpdateProfileRequest, me: dict = Depends(_current_user)):
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """UPDATE users SET display_name=$1, bio=$2 WHERE id=$3
               RETURNING id, username, email, display_name, bio,
                         follower_count, following_count, created_at""",
            req.display_name, req.bio, uuid.UUID(me["user_id"]),
        )
    if not row:
        raise HTTPException(404, "user not found")
    return _row(row, include_email=True)


@app.post("/v1/users/{user_id}/follow", status_code=204)
async def follow(user_id: str, me: dict = Depends(_current_user)):
    follower_id  = uuid.UUID(me["user_id"])
    followee_id  = uuid.UUID(user_id)
    if follower_id == followee_id:
        raise HTTPException(400, "cannot follow yourself")
    async with pool.acquire() as conn:
        async with conn.transaction():
            result = await conn.execute(
                "INSERT INTO follows (follower_id, followee_id) VALUES ($1,$2) ON CONFLICT DO NOTHING",
                follower_id, followee_id,
            )
            # "INSERT 0 0" means already following — skip counter update
            if result == "INSERT 0 0":
                return
            await conn.execute(
                "UPDATE users SET following_count = (SELECT COUNT(*) FROM follows WHERE follower_id=$1) WHERE id=$1",
                follower_id,
            )
            await conn.execute(
                "UPDATE users SET follower_count = (SELECT COUNT(*) FROM follows WHERE followee_id=$1) WHERE id=$1",
                followee_id,
            )
    # Invalidate follower's cached timeline so next load pulls from DB (includes new followee's history)
    if USE_REDIS:
        try:
            await rdb.delete(f"timeline:{me['user_id']}")
        except Exception as e:
            logger.warning("failed to invalidate timeline cache on follow: %s", e)


@app.delete("/v1/users/{user_id}/follow", status_code=204)
async def unfollow(user_id: str, me: dict = Depends(_current_user)):
    follower_id = uuid.UUID(me["user_id"])
    followee_id = uuid.UUID(user_id)
    async with pool.acquire() as conn:
        async with conn.transaction():
            result = await conn.execute(
                "DELETE FROM follows WHERE follower_id=$1 AND followee_id=$2",
                follower_id, followee_id,
            )
            if result == "DELETE 0":
                return  # already not following, nothing to update
            await conn.execute(
                "UPDATE users SET following_count = (SELECT COUNT(*) FROM follows WHERE follower_id=$1) WHERE id=$1",
                follower_id,
            )
            await conn.execute(
                "UPDATE users SET follower_count = (SELECT COUNT(*) FROM follows WHERE followee_id=$1) WHERE id=$1",
                followee_id,
            )
    # Invalidate follower's cached timeline so their feed no longer shows unfollowed user's tweets
    if USE_REDIS:
        try:
            await rdb.delete(f"timeline:{me['user_id']}")
        except Exception as e:
            logger.warning("failed to invalidate timeline cache on unfollow: %s", e)


# ── Internal endpoint (called by tweet fanout worker) ─────────────────────────
@app.get("/v1/users/{user_id}/followers/ids")
async def get_follower_ids(
    user_id:  str,
    limit:    int = 500,
    after_id: Optional[str] = None,
):
    uid = uuid.UUID(user_id)
    async with pool.acquire() as conn:
        if after_id:
            rows = await conn.fetch(
                """SELECT follower_id FROM follows
                   WHERE followee_id=$1 AND follower_id > $2
                   ORDER BY follower_id LIMIT $3""",
                uid, uuid.UUID(after_id), limit,
            )
        else:
            rows = await conn.fetch(
                "SELECT follower_id FROM follows WHERE followee_id=$1 ORDER BY follower_id LIMIT $2",
                uid, limit,
            )
    return {"ids": [str(r["follower_id"]) for r in rows]}


@app.get("/health")
async def health():
    return {"status": "ok"}
