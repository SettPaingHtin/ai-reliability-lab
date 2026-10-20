# AI Reliability Lab

Evaluate AI applications, track results per run, and (next milestones) catch regressions in CI.
Milestone 1 is a working vertical slice: **project → dataset (JSONL) → run against a deterministic mock provider → persisted results → failure inspection in the UI.**

## Status — be precise about what works
| Area | Status |
|---|---|
| Domain core (scoring, JSONL validation, mock provider, concurrent engine with retries/timeouts/rate limiting, metrics) | Implemented; **45 unit tests verified passing** |
| FastAPI API, SQLAlchemy models, Alembic migration, API integration tests | Implemented; **not yet executed** (see below) |
| Next.js UI (projects, datasets, import, run results, failure details) | Implemented; **not yet built or run** |
| Run comparison, thresholds, CLI, Celery/Redis, real providers, AI grading, user auth, benchmarks, GitHub Actions PR-eval example | **Not started** (see `docs/architecture.md`) |

The environment this was written in had no network, Docker, Postgres, FastAPI, or pytest, so only the framework-free domain tests, a strict `tsc` check of `frontend/lib`, and the formatter assertions were actually run. Expect to fix small integration issues on first run and treat the API/UI layers as unverified until your own test run passes.

## Quick start (Docker)
```bash
cp .env.example .env            # set POSTGRES_PASSWORD; set API_KEY (openssl rand -hex 32) for anything beyond local use
docker compose up --build
```
UI: http://localhost:3000 · API docs (OpenAPI): http://localhost:8000/docs · Readiness: http://localhost:8000/health/ready

Then: create a project → create a dataset → import `datasets/sample.jsonl` → **Run evaluation (mock)** → open the run and expand failed cases.

## Local development
```bash
# Backend (Python 3.12). Tests use SQLite, so they need no Postgres.
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest                       # domain + API integration tests
ruff check . && ruff format --check .

# Backend against Postgres
export DATABASE_URL=postgresql+psycopg://arl:change-me-locally@localhost:5432/arl
alembic upgrade head
uvicorn app.main:create_app --factory --reload

# Frontend
cd frontend
npm install                  # then commit package-lock.json
BACKEND_URL=http://localhost:8000 npm run dev
npm run lint && npm run typecheck && npm test
```

## Dataset format (JSONL, one object per line)
```json
{"input": "What is 2 + 2?", "expected": "4"}
{"input": "Name a color", "rules": [{"type": "regex", "value": "red|blue", "case_sensitive": false}]}
{"input": "Summarize…", "context": "…", "rules": [{"type": "contains", "value": "cat"}, {"type": "not_contains", "value": "dog"}]}
```
- Fields: `input` (required), `expected`, `context`, `rules`, `metadata`. Unknown fields are rejected.
- Rule types: `exact` (defaults to `expected`), `contains`, `not_contains`, `regex`; options `case_sensitive` (default true), `strip` (default true).
- A case passes only if **all** rules pass; score is the mean rule score. Import is all-or-nothing and reports every bad line.
- Mock provider controls (in `metadata`): `mock_output`, `mock_latency_ms`, `mock_error` (`error|timeout|rate_limited|flaky:N`), `mock_report_usage: false`.

## Reliability semantics
- Per-case outcomes are `passed`, `failed` (scored below bar), or `error` (provider/scoring failure after retries). Errors don't stop the run.
- Retryable errors (timeout, rate limit, unavailable) back off exponentially up to `max_retries`; others fail immediately.
- Metrics a provider doesn't report are `NULL` and shown as "—"; they are never coerced to 0. Mock-provider cost uses illustrative pricing, not real prices.
- Run execution is claimed atomically, so submitting the same run twice does nothing; re-running a partially completed run resumes remaining cases.

## Configuration
See `.env.example`. Secrets come only from environment variables; the browser never sees the API key (the Next.js server proxies `/api/*`). **Auth is a single shared key — do not expose publicly until real auth ships.**

More detail: [`docs/architecture.md`](docs/architecture.md).
