#!/usr/bin/env python3
"""
Mini-Twitter API smoke test.
Tests every endpoint in dependency order.

Usage:
    python scripts/test_api.py                     # default: http://localhost:8080
    BASE_URL=http://my-alb.aws.com python scripts/test_api.py
"""

import os
import sys
import time
import requests

BASE_URL = os.getenv("BASE_URL", "http://localhost:8080")

# ── Colour helpers ────────────────────────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
RESET  = "\033[0m"
BOLD   = "\033[1m"

passed = failed = 0

def ok(name):
    global passed
    passed += 1
    print(f"  {GREEN}✓{RESET} {name}")

def fail(name, reason):
    global failed
    failed += 1
    print(f"  {RED}✗{RESET} {name}")
    print(f"    {YELLOW}→ {reason}{RESET}")

def section(title):
    print(f"\n{BOLD}{title}{RESET}")

def check(name, resp, expected_status, key=None):
    """Assert status code; optionally assert a key exists in the JSON body."""
    if resp.status_code != expected_status:
        fail(name, f"expected {expected_status}, got {resp.status_code}  body={resp.text[:120]}")
        return None
    # 204 No Content has no body — nothing to parse
    if resp.status_code == 204:
        ok(name)
        return {}
    try:
        data = resp.json()
    except Exception:
        fail(name, f"response is not JSON: {resp.text[:120]}")
        return None
    if key and key not in data:
        fail(name, f"key '{key}' missing in response: {data}")
        return None
    ok(name)
    return data

def check_value(name, actual, expected):
    """Assert that actual == expected."""
    if actual == expected:
        ok(name)
    else:
        fail(name, f"expected {expected!r}, got {actual!r}")

def check_true(name, condition, reason="condition was False"):
    if condition:
        ok(name)
    else:
        fail(name, reason)

# ── HTTP helpers ──────────────────────────────────────────────────────────────
def authed(token):
    return {"Authorization": f"Bearer {token}"}

def post(path, body=None, token=None):
    h = {"Content-Type": "application/json"}
    if token:
        h.update(authed(token))
    return requests.post(BASE_URL + path, json=body, headers=h, timeout=10)

def get(path, token=None):
    h = authed(token) if token else {}
    return requests.get(BASE_URL + path, headers=h, timeout=10)

def put(path, body=None, token=None):
    h = {"Content-Type": "application/json"}
    if token:
        h.update(authed(token))
    return requests.put(BASE_URL + path, json=body, headers=h, timeout=10)

def delete(path, token=None):
    h = authed(token) if token else {}
    return requests.delete(BASE_URL + path, headers=h, timeout=10)

# ─────────────────────────────────────────────────────────────────────────────
print(f"\n{BOLD}Mini-Twitter API Tests{RESET}  →  {BASE_URL}\n")

# ── 0. Health checks ──────────────────────────────────────────────────────────
section("0. Health — all services")

for name, port in [("gateway", 8080), ("user", 8081), ("tweet", 8082), ("timeline", 8083)]:
    r = requests.get(f"http://localhost:{port}/health", timeout=5)
    check(f"{name}-service /health", r, 200)

# ── 1. Auth ───────────────────────────────────────────────────────────────────
section("1. Auth — register & login")

ts = int(time.time())
alice_name = f"alice_{ts}"
bob_name   = f"bob_{ts}"

r = post("/v1/auth/register", {"username": alice_name, "email": f"{alice_name}@test.com", "password": "pass123"})
d = check("Register alice", r, 201, "token")
alice_token = d["token"]      if d else None
alice_id    = d["user"]["id"] if d else None

r = post("/v1/auth/register", {"username": bob_name, "email": f"{bob_name}@test.com", "password": "pass123"})
d = check("Register bob", r, 201, "token")
bob_token = d["token"]      if d else None
bob_id    = d["user"]["id"] if d else None

r = post("/v1/auth/login", {"username": alice_name, "password": "pass123"})
d = check("Login alice", r, 200, "token")
if d:
    alice_token = d["token"]

r = post("/v1/auth/login", {"username": bob_name, "password": "pass123"})
d = check("Login bob", r, 200, "token")
if d:
    bob_token = d["token"]

r = post("/v1/auth/login", {"username": alice_name, "password": "wrongpassword"})
check("Login with wrong password → 401", r, 401)

r = post("/v1/auth/register", {"username": alice_name, "email": f"{alice_name}@test.com", "password": "pass123"})
check("Duplicate register → 409", r, 409)

r = post("/v1/auth/login", {"username": alice_name, "password": "pass123"})
r2 = requests.get(BASE_URL + "/v1/users/me",
                  headers={"Authorization": "Bearer this.is.a.fake.token"}, timeout=10)
check("Forged JWT token → 401", r2, 401)

# ── 2. Users ──────────────────────────────────────────────────────────────────
section("2. Users — profile & follow")

r = get("/v1/users/me", token=alice_token)
check("GET /users/me", r, 200, "username")

r = get(f"/v1/users/{alice_name}")
check("GET /users/{username} (public)", r, 200, "username")

r = put("/v1/users/me", {"display_name": "Alice Test", "bio": "Hello world"}, token=alice_token)
d = check("PUT /users/me (update profile)", r, 200, "display_name")

# Verify update actually persisted
if d:
    r2 = get("/v1/users/me", token=alice_token)
    d2 = r2.json()
    check_value("Profile update persisted (display_name)", d2.get("display_name"), "Alice Test")
    check_value("Profile update persisted (bio)",          d2.get("bio"),          "Hello world")

r = get("/v1/users/me")
check("GET /users/me without token → 401", r, 401)

if alice_id and bob_id:
    # Capture following_count before follow
    before = get("/v1/users/me", token=alice_token).json()

    r = post(f"/v1/users/{bob_id}/follow", token=alice_token)
    check("Alice follows Bob → 204", r, 204)

    # Verify counters incremented
    after_alice = get("/v1/users/me",          token=alice_token).json()
    after_bob   = get(f"/v1/users/{bob_name}").json()
    check_value(
        "Alice following_count +1 after follow",
        after_alice.get("following_count"),
        before.get("following_count", 0) + 1,
    )
    check_value(
        "Bob follower_count +1 after follow",
        after_bob.get("follower_count"),
        1,
    )

    r = post(f"/v1/users/{bob_id}/follow", token=alice_token)
    check("Follow same user again (idempotent) → 204", r, 204)

    r = post(f"/v1/users/{alice_id}/follow", token=alice_token)
    check("Follow yourself → 400", r, 400)

# ── 3. Tweets — CRUD ──────────────────────────────────────────────────────────
section("3. Tweets — CRUD")

tweet_id      = None
bob_tweet_id  = None

if alice_token:
    r = post("/v1/tweets", {"content": "Hello from Alice!"}, token=alice_token)
    d = check("Create tweet (alice)", r, 201, "id")
    if d:
        tweet_id = d["id"]

if bob_token:
    r = post("/v1/tweets", {"content": "Hello from Bob!"}, token=bob_token)
    d = check("Create tweet (bob)", r, 201, "id")
    if d:
        bob_tweet_id = d["id"]

if alice_token:
    r = post("/v1/tweets", {"content": ""}, token=alice_token)
    check("Create tweet with empty content → 400", r, 400)

    r = post("/v1/tweets", {"content": "x" * 281}, token=alice_token)
    check("Create tweet >280 chars → 400", r, 400)

    r = post("/v1/tweets", {"content": "No auth tweet"})
    check("Create tweet without token → 401", r, 401)

if tweet_id:
    r = get(f"/v1/tweets/{tweet_id}")
    check("GET /tweets/{id} (public)", r, 200, "content")

# Reply tweet (reply_to_id)
reply_id = None
if tweet_id and bob_token:
    r = post("/v1/tweets", {"content": "Replying to Alice!", "reply_to_id": tweet_id}, token=bob_token)
    d = check("Create reply tweet (reply_to_id)", r, 201, "id")
    if d:
        reply_id = d["id"]
        check_value("reply_to_id stored correctly", d.get("reply_to_id"), tweet_id)

# ── 4. Likes ──────────────────────────────────────────────────────────────────
section("4. Likes — count verification")

if tweet_id and alice_token:
    r = post(f"/v1/tweets/{tweet_id}/like", token=alice_token)
    check("Like a tweet → 204", r, 204)

    r = post(f"/v1/tweets/{tweet_id}/like", token=alice_token)
    check("Like again (idempotent via ON CONFLICT) → 204", r, 204)

    # Give eventual-consistency aggregator a moment (or check Redis count directly)
    time.sleep(0.5)
    r = get(f"/v1/tweets/{tweet_id}")
    d = r.json()
    check_true(
        "like_count > 0 after liking",
        d.get("like_count", 0) > 0,
        f"like_count is {d.get('like_count')}, expected > 0",
    )

    r = delete(f"/v1/tweets/{tweet_id}/like", token=alice_token)
    check("Unlike a tweet → 204", r, 204)

# ── 5. Timeline — fanout chain ────────────────────────────────────────────────
section("5. Timeline — fanout & feed")

if alice_token:
    # Alice follows Bob (already done in section 2); Bob has tweeted.
    # Wait for fanout worker to push Bob's tweet into Alice's Redis timeline.
    time.sleep(1)

    r = get("/v1/timeline/home", token=alice_token)
    d = check("GET /timeline/home", r, 200, "tweets")
    if d:
        tweets = d.get("tweets") or []
        check_true(
            "Home timeline contains Bob's tweet (fanout worked)",
            any(t.get("user_id") == bob_id for t in tweets),
            f"Bob's tweet not found in Alice's feed. Got {len(tweets)} tweet(s).",
        )

    r = get("/v1/timeline/home")
    check("GET /timeline/home without token → 401", r, 401)

if bob_id:
    r = get(f"/v1/timeline/user/{bob_id}")
    d = check("GET /timeline/user/{id} (public)", r, 200, "tweets")
    if d:
        tweets = d.get("tweets") or []
        check_true(
            "User timeline contains Bob's own tweet",
            len(tweets) > 0,
            "Bob's user timeline is empty",
        )

# ── 6. Delete tweet ───────────────────────────────────────────────────────────
section("6. Delete tweet")

if tweet_id and alice_token and bob_token:
    r = delete(f"/v1/tweets/{tweet_id}", token=bob_token)
    check("Delete someone else's tweet → 404", r, 404)

    r = delete(f"/v1/tweets/{tweet_id}", token=alice_token)
    check("Delete own tweet → 204", r, 204)

    r = get(f"/v1/tweets/{tweet_id}")
    check("GET deleted tweet → 404", r, 404)

# ── 7. Unfollow ───────────────────────────────────────────────────────────────
section("7. Unfollow — counter verification")

if alice_token and bob_id and bob_name:
    before_alice = get("/v1/users/me",          token=alice_token).json()
    before_bob   = get(f"/v1/users/{bob_name}").json()

    r = delete(f"/v1/users/{bob_id}/follow", token=alice_token)
    check("Alice unfollows Bob → 204", r, 204)

    after_alice = get("/v1/users/me",          token=alice_token).json()
    after_bob   = get(f"/v1/users/{bob_name}").json()

    check_value(
        "Alice following_count -1 after unfollow",
        after_alice.get("following_count"),
        before_alice.get("following_count", 1) - 1,
    )
    check_value(
        "Bob follower_count -1 after unfollow",
        after_bob.get("follower_count"),
        before_bob.get("follower_count", 1) - 1,
    )

    r = delete(f"/v1/users/{bob_id}/follow", token=alice_token)
    check("Unfollow again (idempotent) → 204", r, 204)

# ── Summary ───────────────────────────────────────────────────────────────────
total = passed + failed
print(f"\n{'─'*40}")
print(f"  {GREEN}{passed} passed{RESET}  {RED}{failed} failed{RESET}  ({total} total)")
print(f"{'─'*40}\n")

sys.exit(0 if failed == 0 else 1)
