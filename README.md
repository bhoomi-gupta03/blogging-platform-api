# Blogging Platform API

A REST API where users register, log in with JWT authentication, and manage blog posts. Anyone can read posts; only a post's owner can edit or delete it.

> **Status:** portfolio project. The automated tests run on an in-memory SQLite database. PostgreSQL is supported through SQLAlchemy and documented below, but is not covered by the automated tests. Run the tests yourself before describing the project as finished.

## Problem statement

Blog backends need two things done correctly: knowing *who* is calling (authentication) and deciding *what they may do* (authorization). This project implements both with a small, readable codebase.

## Features

- `GET /health` health check
- Registration with validation, duplicate detection, and Argon2 password hashing
- Login that returns a signed, expiring JWT access token
- Create, list (paginated), read, update and delete posts
- Ownership checks: users cannot modify each other's posts
- Settings loaded from `.env`; the app refuses to start with a missing or weak JWT secret
- 39 pytest tests using an isolated in-memory database

## Tech stack

Python 3.11+, FastAPI, Uvicorn, SQLAlchemy 2.x, Pydantic v2 + pydantic-settings, PyJWT, pwdlib (Argon2), SQLite or PostgreSQL (psycopg 3), pytest + httpx.

## Architecture

```
app/
  main.py          App, lifespan (creates tables), router registration, logging
  config.py        Settings from environment/.env with startup validation
  database.py      Engine, session factory, get_db dependency
  models.py        User and Post tables
  schemas.py       Pydantic request/response models
  security.py      Password hashing and JWT create/verify
  dependencies.py  get_current_user (token -> user)
  routers/
    auth.py        POST /auth/register, POST /auth/login
    posts.py       Post CRUD and ownership checks
tests/             pytest suite (own in-memory database, own test secret)
```

A router handles HTTP and delegates to small helpers; there is no separate service layer because the handlers are short.

## Database schema

```mermaid
erDiagram
    USERS ||--o{ POSTS : writes
    USERS {
        int id PK
        string username UK
        string email UK
        string hashed_password
        datetime created_at
    }
    POSTS {
        int id PK
        string title
        text content
        datetime created_at
        datetime updated_at
        int owner_id FK
    }
```

**User deletion policy:** deleting a user deletes their posts (ORM cascade plus `ON DELETE CASCADE`). There is no delete-user endpoint yet; the policy is covered by a test in `tests/test_models.py`.

## Prerequisites

- Python 3.11 or newer
- Git
- PostgreSQL 14+ (optional; SQLite works out of the box)

## Setup on Windows (PowerShell)

```powershell
cd blogging-platform-api
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
Copy-Item .env.example .env
```

If PowerShell blocks activation: `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`, then activate again.

### Create your JWT secret

```powershell
python -c "import secrets; print(secrets.token_hex(32))"
```

Open `.env` and paste the output as the value of `JWT_SECRET`. The app **will not start** if it is missing, shorter than 32 characters, or still the placeholder. Never commit `.env`.

### Optional: PostgreSQL

In `psql` (run `psql -U postgres`):

```sql
CREATE USER blog_user WITH PASSWORD 'choose-a-strong-password';
CREATE DATABASE blogging_platform OWNER blog_user;
```

Then set this in `.env`:

```text
DATABASE_URL=postgresql+psycopg://blog_user:choose-a-strong-password@localhost:5432/blogging_platform
```

Common problems: `psql` not found (add PostgreSQL's `bin` folder to PATH), connection refused (PostgreSQL service not running or wrong port), authentication failed (wrong password in the URL; special characters in a password must be URL-encoded).

## Run

```powershell
uvicorn app.main:app --reload
```

- Health: http://127.0.0.1:8000/health
- Swagger UI: http://127.0.0.1:8000/docs
- Port busy? Use `--port 8001`.

Tables are created at startup if missing (nothing is ever dropped). This suits local development; use Alembic migrations before changing schemas in production.

## Run the tests

```powershell
pytest -v
```

`tests/conftest.py` sets its own `DATABASE_URL` (in-memory SQLite) and `JWT_SECRET` before the app is imported, so tests never touch your real database or secret.

## Authenticate in Swagger UI

1. `POST /auth/register` with a username, email and password.
2. Click **Authorize** (top right), enter that username and password, and confirm. Swagger calls `/auth/login` and attaches the token to later requests.
3. Try `POST /posts`.

## Endpoints

| Method | Path | Auth | Description |
|---|---|:---:|---|
| GET | `/health` | no | Process is up |
| POST | `/auth/register` | no | Create account |
| POST | `/auth/login` | no | Form fields `username`, `password` → token |
| POST | `/posts` | yes | Create a post |
| GET | `/posts?limit=10&offset=0` | no | Newest first; `limit` 1–100 |
| GET | `/posts/{id}` | no | One post |
| PUT | `/posts/{id}` | owner | Replace title and content (both required) |
| DELETE | `/posts/{id}` | owner | Delete (204) |

Usernames and emails are case-insensitive (stored lowercase). Titles are 1–200 characters and content 1–20000 characters, after trimming whitespace.

**Register**

```json
POST /auth/register
{"username": "writer01", "email": "writer@example.com", "password": "use-a-strong-password"}

201
{"id": 1, "username": "writer01", "email": "writer@example.com", "created_at": "2026-10-29T10:00:00Z"}
```

**Login**

```json
POST /auth/login   (form: username=writer01&password=...)

200
{"access_token": "<jwt>", "token_type": "bearer"}
```

**Create post** (header `Authorization: Bearer <jwt>`)

```json
POST /posts
{"title": "My first post", "content": "Hello world"}

201
{"id": 1, "title": "My first post", "content": "Hello world", "created_at": "...", "updated_at": "...", "owner_id": 1}
```

**Errors** use FastAPI's format, `{"detail": "..."}`; validation errors return a list under `detail`.

| Status | When |
|---|---|
| 401 | Missing, invalid, expired or wrongly signed token; bad login |
| 403 | Editing or deleting someone else's post |
| 404 | Post does not exist |
| 409 | Username or email already registered |
| 422 | Invalid input (including bad pagination values) |

## How JWT authentication works

```mermaid
sequenceDiagram
    participant C as Client
    participant A as API
    participant D as Database
    C->>A: POST /auth/login (username, password)
    A->>D: find user
    A->>A: verify Argon2 hash
    A-->>C: JWT (sub = user id, exp = now + 30 min), signed with JWT_SECRET
    C->>A: POST /posts + Authorization: Bearer JWT
    A->>A: verify signature and expiry, read sub
    A->>D: load user by sub
    A-->>C: 201 (post owner = that user)
```

## Authorization rules

- The caller is identified **only** from the signed token. A user ID in a request body is ignored (there is a test for this).
- Reading posts is public. Creating requires login. Updating and deleting require being the owner.
- A missing post returns **404**. Someone else's post returns **403**. Posts are public to read, so their existence is not secret and 403 gives the clearest message.

## Security decisions

- Passwords: Argon2 via `pwdlib`; hashes are never returned.
- JWT: HS256 fixed in code, `exp` and `sub` required, secret loaded from the environment and validated at startup.
- Login returns the same error for unknown users and wrong passwords, and verifies a dummy hash for unknown users to reduce timing differences.
- Database access goes through the ORM with bound parameters (no string-built SQL).
- Logs contain user and post IDs only: no passwords, tokens or secrets.

## Known limitations

- No refresh tokens, logout or token revocation; tokens are valid until they expire.
- No rate limiting, email verification or password reset.
- No Alembic migrations; schema changes need manual handling.
- No delete-user or profile endpoints.
- No "published/draft" status: all posts are public.
- PostgreSQL is not covered by the automated tests.
- Timing-attack mitigation on login is best-effort, not guaranteed.

## Future enhancements

Alembic migrations, a PostgreSQL test job in CI, post tags and search, comments, refresh tokens, rate limiting, Docker.

## Upload to GitHub

Create an empty repository on GitHub (no README or license), then:

```powershell
git init
git add .
git status          # check: no .env, no .venv, no *.db
git commit -m "Blogging Platform API with JWT auth and post ownership checks"
git branch -M main
git remote add origin https://github.com/<your-username>/blogging-platform-api.git
git push -u origin main
```

Before committing, replace `<YOUR FULL NAME>` in `LICENSE`.
