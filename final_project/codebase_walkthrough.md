# Codebase Walkthrough

## Architecture Overview

A microservices-based Twitter clone built with Python (FastAPI) and deployed on AWS using CDK.
4 containerized services sit behind an Application Load Balancer; inter-service communication
uses AWS Cloud Map private DNS.

```
Browser → S3 (React frontend)
       → ALB → Gateway :8080
                  ├── Cloud Map → User Service    :8081
                  ├── Cloud Map → Tweet Service   :8082
                  └── Cloud Map → Timeline Service :8083

Tweet / Timeline / User Service → RDS PostgreSQL 16
Tweet / Timeline Service        → ElastiCache Redis 7
```

---

## Services

### 1. Gateway (`services/gateway/main.py`)
- **Purpose**: Single entry point; routes all `/v1/*` traffic to the correct downstream service
- **Rate limiting**: Redis-backed per-IP counter (default 5 000 req/min), returns HTTP 429
- **Routing**: `httpx.AsyncClient` reverse proxy with path-prefix matching
- **Port**: 8080

### 2. User Service (`services/user/main.py`)
- **Purpose**: Authentication, profiles, follow/unfollow relationships
- **Auth**: bcrypt password hashing, HS256 JWT tokens (24 h expiry)
- **Follow logic**: `INSERT … ON CONFLICT DO NOTHING` + idempotency check; follower/following
  counts recalculated from `follows` table on every follow/unfollow (self-healing counters)
- **Cache invalidation**: Deletes `timeline:{user_id}` from Redis on follow/unfollow so the
  next home-feed load triggers a DB fallback that includes the new followee's history
- **Schema migrations**: Embedded in Python; run automatically on startup via `IF NOT EXISTS`
- **Port**: 8081

### 3. Tweet Service (`services/tweet/main.py`)
- **Purpose**: Tweet CRUD, likes, fan-out, like aggregation
- **Fan-out-on-write**: `asyncio.Queue` with 5 worker coroutines; each new tweet is pushed
  to the author's own Redis timeline key, then paginated through followers (500 at a time)
  and pushed via Redis pipeline `LPUSH / LTRIM / EXPIRE`
- **Like consistency modes**:
  - `CONSISTENCY_MODE=strong` — synchronous `UPDATE tweets SET like_count` in PostgreSQL
  - `CONSISTENCY_MODE=eventual` *(default)* — `INCR like_count:{id}` in Redis + durable row
    in `like_count_pending`; background aggregator flushes every 30 s then drains Redis counter
- **Idempotency**: `INSERT … ON CONFLICT DO NOTHING` result checked before any counter update
- **Batch endpoint**: `POST /v1/tweets/batch` with optional `viewer_id` returns `liked_by_me`
  per tweet (used by timeline service for correct like-button state)
- **Port**: 8082

### 4. Timeline Service (`services/timeline/main.py`)
- **Purpose**: Serves home and user timelines
- **Home feed strategy**:
  1. Redis-first: `LRANGE timeline:{user_id}` (O(1) read)
  2. Cache miss → DB fallback: `SELECT … WHERE user_id = ANY(followees + self)`
  3. After DB fallback: async cache write-back (`_write_back_cache`) so subsequent reads are fast
- **Cache**: 1 000 tweets per key, 24 h TTL (matches tweet service fan-out settings)
- **Enrichment**: calls `POST /v1/tweets/batch` on tweet service (passes `viewer_id` for like state)
- **Port**: 8083

---

## Data Layer

### PostgreSQL Schema (`db/migrations/`)
| Table | Purpose |
|-------|---------|
| `users` | Credentials, profile, denormalized follower/following counts |
| `tweets` | Content, `like_count`, optional `reply_to_id` |
| `follows` | Many-to-many follower relationships (composite PK) |
| `likes` | User ↔ tweet like records (composite PK, prevents duplicates) |
| `like_count_pending` | Durable delta buffer for eventual-consistency like aggregation |

### Redis Key Space
| Key pattern | Type | Purpose |
|-------------|------|---------|
| `timeline:{user_id}` | List | Pre-built tweet-ID list for home feed (fan-out-on-write) |
| `like_count:{tweet_id}` | String | Pending like delta (drained by aggregator every 30 s) |
| `ratelimit:{ip}` | String | Per-IP request counter (1-minute window) |

---

## AWS Infrastructure (CDK — `cdk/`)

| Stack | Resources |
|-------|-----------|
| **NetworkStack** | VPC (2 AZs, 1 NAT), Security Groups for RDS and Redis |
| **DatabaseStack** | RDS PostgreSQL 16 t3.micro, ElastiCache Redis 7 t3.micro |
| **ContainerStack** | ECS Fargate × 4, ALB (path-based routing), Cloud Map namespace |
| **FrontendStack** | S3 static website hosting the React build |

### Key design decisions
- **ECS SG lives in ContainerStack** (not NetworkStack) to avoid cyclic CloudFormation references
  between the ALB security group and the ECS task security group
- **DB credentials** injected via Secrets Manager (`DB_PASSWORD` field); services assemble the
  connection URL from individual env vars at runtime
- **Cloud Map** (`mini-twitter.local`) provides private DNS for inter-service calls
  (e.g. `http://user-service.mini-twitter.local:8081`) without routing through the public internet
- **Docker images** built with `platform=LINUX_AMD64` to ensure compatibility with Fargate
  when developing on Apple Silicon

---

## Frontend (`frontend/src/`)

| Component | Purpose |
|-----------|---------|
| `App.jsx` | Tab navigation (Home / Users / Profile), auth state, refresh trigger |
| `Auth.jsx` | Login / register form |
| `Feed.jsx` | Home timeline, like toggle (persists `liked_by_me` across refreshes), delete |
| `TweetBox.jsx` | Compose tweet, 280-char counter, auto-refreshes feed on post |
| `UserSearch.jsx` | Search by username, follow/unfollow with correct initial state from `you_follow` |
| `Profile.jsx` | View/edit profile, own tweet list with delete |
| `api.js` | Centralised fetch wrapper; reads `VITE_API_BASE_URL` for prod ALB URL |

---

## Local Development

```bash
docker compose up --build   # starts postgres + redis + all 4 services
python scripts/test_api.py  # runs 46 API tests
```
