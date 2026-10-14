# Backend Requirements

## Runtime

- Python 3.14 with [`uv`](https://docs.astral.sh/uv/)
- PostgreSQL and Redis
- Git and `rg` (ripgrep) available to worker processes
- A writable target Git repository with a configured base branch

## Environment

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | Async PostgreSQL connection |
| `REDIS_URL` | Celery broker connection |
| `OPENAI_API_KEY` | Agent model access |
| `GITHUB_TOKEN` | Issue intake and draft pull-request publication |
| `CORS_ORIGINS` | Allowed frontend origins |

The selected repository must define an allowed test command. The bundled fixture uses `backend/` with `uv run pytest -q`; generated worktrees are stored outside the target checkout and are removed at terminal workflow states.

For the GitHub flow, use a fine-grained token with repository **Contents: read/write**, **Issues: read**, and **Pull requests: read/write** permissions. The current clone step supports public HTTPS repositories; the token is used for issue API access, pushing the approved result branch, and creating the draft pull request.

## Commands

```bash
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
uv run celery -A app.tasks.celery_app:celery_app worker --beat --loglevel=INFO --pool=solo
uv run pytest
uv run ruff check .
```

Docker Compose starts PostgreSQL and Redis. During local development, run the API and Celery worker as separate processes from `backend/`; `--pool=solo` keeps worker execution sequential and easier to debug, while `--beat` schedules stale-workflow recovery. A deployed system should run Celery Beat as a separate process. Inspect the repository MCP server with `uv run mcp dev run_mcp.py`.

## Constraints

- Repository commands require an execution sandbox before accepting arbitrary untrusted code.
- Workstream paths guide decomposition but do not replace worktree isolation or merge-conflict handling.
- PostgreSQL is the durable source of workflow state; Redis and SSE must not be treated as persistence.
- Database state changes and Celery publication are not transactional; a production version should use a transactional outbox to close the commit-before-publish crash window.
- Git push, draft-PR creation, and the final database commit are separate operations; production retries would need idempotent publication and reconciliation for partial failures.
