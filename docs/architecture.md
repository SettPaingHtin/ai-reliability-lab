# Architecture

## Goals
Reproducible AI regression testing, simple enough for one developer to hold in their head.

## Layers (dependency direction: top → bottom)
```
frontend (Next.js)  ──/api proxy (server-side, holds API key)──▶  FastAPI routes  (app/api)
                                                                      │ validation, auth, pagination
                                                                  services (app/services)   run lifecycle, DB access
                                                                      │
                                                  domain (app/domain)  ← pure Python, no I/O frameworks
                                                  scoring · jsonl · providers · engine
                                                                      │
                                                  persistence (app/models, Alembic) → PostgreSQL
```
`app/domain` imports nothing from FastAPI/SQLAlchemy. It is unit-tested in isolation and will be reused by the CLI and workers unchanged.

## Key decisions
| Decision | Why |
|---|---|
| Domain core is framework-free | Fast deterministic tests; CLI/worker reuse; no hidden coupling. |
| Engine yields outcomes; caller persists | Results are committed one at a time, so a crash keeps partial progress. No DB session is held during provider calls. |
| `queued → running` claim is a single conditional `UPDATE … WHERE status='queued'` | Exactly one executor wins; duplicate submissions are no-ops, on any DB, without advisory locks. |
| `UNIQUE(run_id, case_id)` + "skip cases that already have results" | Re-executing a crashed run resumes instead of duplicating. |
| Results snapshot input/expected/rules; `case_id` is `ON DELETE SET NULL` | Historical runs stay reproducible and readable even if the dataset changes. |
| Unavailable metrics are `NULL`, never `0` | Aggregates are `NULL` when no row reported the metric; the UI shows "—". Zero is a measured value. |
| Deterministic scoring and (future) AI grading stored separately (`score_details.kind`) | AI judgments are suggestions, never mixed into verified checks. |
| Mock provider driven by per-case `metadata.mock_*` | Deterministic demos/tests of success, failure, timeout, flaky retry, and missing-usage paths without API keys. |
| FastAPI `BackgroundTasks` for milestone 1 | Simplest thing that works end to end. **Not durable** across process restarts; replaced by Celery + Redis in milestone 2 (`execute_run` is already idempotent and worker-safe). |
| Frontend proxies `/api/*` server-side | The API key and backend URL never reach the browser; upstream host is fixed by env (no user-controlled URLs → no SSRF). |

## Security posture (milestone 1)
- Dataset content is data only. It is passed to providers and never interpreted by the platform.
- Regex rules: pattern length capped, output truncated to 20k chars before matching. Python's `re` has no timeout, so catastrophic-backtracking patterns remain a residual risk until rule execution is sandboxed (planned).
- Import size, line count, and field sizes are capped. Errors never echo prompts. Logs record method/path/status/duration only.
- Auth is a **single shared API key** (`X-API-Key`, constant-time compare). There are no user accounts or per-project ownership yet, so **do not expose the app publicly**. Multi-user auth and project-level authorization are a required milestone before any public deployment.

## Known limitations / next milestones
1. Run comparison + thresholds (regressions, recoveries, score deltas) and CLI exit codes.
2. Celery + Redis workers, stuck-`running` run recovery, run-level cancel.
3. Second real provider adapter (fixed, env-configured base URL), AI-assisted grading with rubrics.
4. Real user auth and per-project authorization.
5. Benchmark script (throughput, latency percentiles, queue behavior) reporting only measured numbers.
6. Lockfiles (`uv.lock`/`requirements`, `package-lock.json`) — not yet generated.
