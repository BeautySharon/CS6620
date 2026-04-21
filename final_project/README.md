# Distributed Mini Twitter on AWS

A cloud-native Twitter-like application built with microservices, deployed on AWS. Users can register, post tweets, follow other users, view a personalized home timeline, like tweets, and edit their profile.

---

## Architecture

```
Browser (React SPA on S3)
        |
        v
Application Load Balancer  (path-based routing /v1/*)
        |
   [Gateway :8080]  ──── Redis rate limiting (sliding window per IP)
        |
        ├── /v1/auth/*  /v1/users/*  ──> [User Service    :8081]
        ├── /v1/tweets  /v1/tweets/* ──> [Tweet Service   :8082]
        └── /v1/timeline/*           ──> [Timeline Service :8083]

[User Service]     ─── asyncpg ──> PostgreSQL (users, follows)
                   ─── redis ───> Invalidate timeline cache on follow/unfollow

[Tweet Service]    ─── asyncpg ──> PostgreSQL (tweets, likes)
                   ─── redis ───> Fan-out worker pushes tweet IDs to follower timelines
                                  Like aggregator: Redis INCR → periodic batch flush to DB

[Timeline Service] ─── redis ───> lrange(timeline:{user_id})  (primary cache)
                   ─── asyncpg ──> PostgreSQL fallback on cache miss
                   ─── httpx ───> Tweet Service /v1/tweets/batch (hydrate tweet IDs)
```

### AWS Infrastructure (4 CDK Stacks)

| Stack | Resources |
|---|---|
| `NetworkStack` | VPC, 2 AZs, public/private subnets, security groups |
| `DatabaseStack` | RDS PostgreSQL 16 (t3.micro), ElastiCache Redis 7 (t3.micro) |
| `ContainerStack` | ECS Fargate cluster, ALB, Cloud Map private DNS, 4 Fargate services |
| `FrontendStack` | S3 static website hosting |

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 18, Vite 5 |
| Backend | Python 3.12, FastAPI 0.115, Uvicorn |
| Database | PostgreSQL 16 (asyncpg) |
| Cache | Redis 7 (redis.asyncio) |
| Auth | JWT (python-jose, HS256), bcrypt |
| Infrastructure | AWS CDK v2 (Python) |
| Containers | Docker, Docker Compose |
| AWS Services | ECS Fargate, ALB, RDS, ElastiCache, S3, Secrets Manager, CloudWatch, Cloud Map |

---

## Project Structure

```
final_project/
├── cdk/                        # AWS CDK infrastructure as code (Python)
│   ├── app.py                  # CDK entry point — instantiates 4 stacks
│   └── stacks/
│       ├── network_stack.py
│       ├── database_stack.py
│       ├── container_stack.py
│       └── frontend_stack.py
│
├── services/                   # Backend microservices
│   ├── gateway/                # API gateway — rate limiting + request routing
│   ├── user/                   # Auth, profiles, follow/unfollow
│   ├── tweet/                  # Tweet CRUD, likes, fan-out-on-write
│   └── timeline/               # Home & user timeline reads (Redis + DB)
│
├── db/
│   └── migrations/             # PostgreSQL schema (000–004)
│
├── frontend/                   # React SPA (deployed to S3)
│   └── src/
│       ├── App.jsx
│       ├── api.js
│       └── components/         # Auth, Feed, Profile, TweetBox, UserSearch
│
├── scripts/
│   └── test_api.py             # Smoke test suite (7 sections)
│
└── docker-compose.yml          # Local development orchestration
```

---

## Services

### Gateway (`services/gateway/`)
- Routes all `/v1/{path}` requests to the appropriate upstream service
- Rate limiting via Redis sliding-window counter (`rate_limit:{ip}:{minute}`, default 5000 RPM)
- Fails open on Redis errors (does not block traffic)

### User Service (`services/user/`)
- Handles registration, login, JWT auth, user profiles, follow/unfollow
- Runs schema migrations idempotently at startup
- Heals `follower_count` / `following_count` from the `follows` table on startup
- On follow/unfollow, invalidates the follower's Redis timeline cache

### Tweet Service (`services/tweet/`)
- Tweet creation triggers fan-out: 5 concurrent async workers push the tweet ID into each follower's Redis `timeline:{user_id}` list (max 1000 entries, 24h TTL)
- Two consistency modes via `CONSISTENCY_MODE` env var:
  - `strong`: direct `UPDATE tweets SET like_count` in PostgreSQL
  - `eventual` (default): Redis `INCR like_count:{tweet_id}` + `like_count_pending` staging table; background task flushes deltas to PostgreSQL every 30 seconds
- Internal `POST /v1/tweets/batch` endpoint used by Timeline Service to hydrate tweet IDs

### Timeline Service (`services/timeline/`)
- Home timeline: Redis first (`LRANGE timeline:{user_id} 0 49`), PostgreSQL fallback on cache miss, async write-back to Redis
- User timeline: always reads from PostgreSQL
- Calls Tweet Service batch endpoint to resolve tweet details and `liked_by_me` for the requesting viewer

---

## Database Schema

| Table | Description |
|---|---|
| `users` | UUID PK, username, email, bcrypt hash, display_name, bio, follower/following counts |
| `tweets` | UUID PK, user_id FK, content (max 280 chars), like_count, reply_to_id (nullable self-ref) |
| `follows` | Composite PK (follower_id, followee_id) |
| `likes` | Composite PK (user_id, tweet_id) |
| `like_count_pending` | Staging table for eventual-consistency like count deltas |

---

## Local Development

**Prerequisites:** Docker, Docker Compose

```bash
# Start all services (PostgreSQL, Redis, gateway, user, tweet, timeline)
docker compose up --build

# Run smoke tests against the local stack
python scripts/test_api.py
```

Services will be available at:
- Gateway API: `http://localhost:8080/v1/`
- Frontend dev server: `http://localhost:5173` (run `npm install && npm run dev` inside `frontend/`)

---

## AWS Deployment

**Prerequisites:** AWS CLI configured, Node.js (for CDK), Python 3.12

```bash
# Install CDK dependencies
cd cdk
pip install -r requirements.txt

# Bootstrap CDK (first time only)
cdk bootstrap

# Deploy all stacks in order
cdk deploy --all
```

Stacks deploy in dependency order: `NetworkStack` → `DatabaseStack` → `ContainerStack` → `FrontendStack`.

After deployment, find the ALB DNS name from the `ContainerStack` outputs and set it as `VITE_API_BASE_URL` when building the frontend:

```bash
cd frontend
VITE_API_BASE_URL=http://<alb-dns> npm run build
```

Then re-deploy `FrontendStack` to sync the updated build to S3.

---

## API Overview

All routes go through the Gateway at `/v1/`.

| Method | Path | Service | Description |
|---|---|---|---|
| POST | `/v1/auth/register` | User | Register new user |
| POST | `/v1/auth/login` | User | Login, returns JWT |
| GET/PUT | `/v1/users/me` | User | Get or update own profile |
| GET | `/v1/users/{username}` | User | Get user by username |
| POST/DELETE | `/v1/users/{user_id}/follow` | User | Follow / unfollow |
| POST | `/v1/tweets` | Tweet | Create tweet |
| GET/DELETE | `/v1/tweets/{id}` | Tweet | Get or delete tweet |
| POST/DELETE | `/v1/tweets/{id}/like` | Tweet | Like / unlike |
| GET | `/v1/timeline/home` | Timeline | Home timeline (auth required) |
| GET | `/v1/timeline/user/{user_id}` | Timeline | User's tweet list |
