# NexoIA — Monorepo Restructure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Relocate the `src/nexoia/` flat package into a `apps/api/` workspace, splitting it into `agent/`, `shared/`, and `interface/` top-level packages so the codebase is ready for multi-app monorepo growth.
**Architecture:** The new layout replaces the single `nexoia` Python package with three sibling packages (`agent`, `shared`, `interface`) rooted at `apps/api/src/`. LangGraph runtime files and skills move to `agent/`; domain, adapters, config, memory, and application logic move to `shared/`; HTTP and worker entry-points move to `interface/` and the `apps/api/src/` root. Config files (`pyproject.toml`, `alembic.ini`, `Dockerfile`) are scoped to `apps/api/` while `docker-compose.yml`, `scripts/`, and `uv.lock` remain at the repo root.
**Tech Stack:** Python 3.11, uv (workspace), hatchling, LangGraph, FastAPI, Alembic/SQLAlchemy, pytest, git mv

---

## Task 1 — Create `apps/api/` directory skeleton

- [ ] Create all target directories:

```bash
mkdir -p apps/api/src/agent/guards
mkdir -p apps/api/src/agent/skills
mkdir -p apps/api/src/shared/domain/policies
mkdir -p apps/api/src/shared/adapters
mkdir -p apps/api/src/shared/config
mkdir -p apps/api/src/shared/memory
mkdir -p apps/api/src/shared/application
mkdir -p apps/api/src/interface
mkdir -p apps/api/tests
mkdir -p apps/api/migrations
```

- [ ] Create all `__init__.py` files so each directory is a proper Python package:

```bash
touch apps/api/src/__init__.py
touch apps/api/src/agent/__init__.py
touch apps/api/src/agent/guards/__init__.py
touch apps/api/src/agent/skills/__init__.py
touch apps/api/src/shared/__init__.py
touch apps/api/src/shared/domain/__init__.py
touch apps/api/src/shared/domain/policies/__init__.py
touch apps/api/src/shared/adapters/__init__.py
touch apps/api/src/shared/config/__init__.py
touch apps/api/src/shared/memory/__init__.py
touch apps/api/src/shared/application/__init__.py
touch apps/api/src/interface/__init__.py
```

- [ ] Commit:

```bash
git add apps/
git commit -m "chore: scaffold apps/api/ directory skeleton"
```

---

## Task 2 — Move agent files

Move LangGraph runtime files with renames, system_prompt, guards, and skills.

- [ ] Move LangGraph runtime files (with renames):

```bash
git mv src/nexoia/infrastructure/langgraph_runtime/graph_builder.py apps/api/src/agent/graph.py
git mv src/nexoia/infrastructure/langgraph_runtime/nodes.py          apps/api/src/agent/react_node.py
git mv src/nexoia/infrastructure/langgraph_runtime/state.py          apps/api/src/agent/state.py
git mv src/nexoia/infrastructure/langgraph_runtime/checkpointer.py   apps/api/src/agent/checkpointer.py
```

- [ ] Move system prompt:

```bash
git mv src/nexoia/infrastructure/llm/system_prompt.py apps/api/src/agent/prompt.py
```

- [ ] Move guards (file by file, preserving `__init__.py`):

```bash
git mv src/nexoia/domain/policies/guards/__init__.py    apps/api/src/agent/guards/__init__.py
git mv src/nexoia/domain/policies/guards/legal_mention.py apps/api/src/agent/guards/legal_mention.py
git mv src/nexoia/domain/policies/guards/loop_detector.py apps/api/src/agent/guards/loop_detector.py
# Note: frustration.py was deleted by the BaseTool refactor plan — skip if it no longer exists
git mv src/nexoia/domain/policies/guards/frustration.py   apps/api/src/agent/guards/frustration.py 2>/dev/null || true
```

- [ ] Move skills (flat — no reorganization yet):

```bash
git mv src/nexoia/infrastructure/skills/__init__.py  apps/api/src/agent/skills/__init__.py
git mv src/nexoia/infrastructure/skills/access.py   apps/api/src/agent/skills/access.py
git mv src/nexoia/infrastructure/skills/refund.py   apps/api/src/agent/skills/refund.py
git mv src/nexoia/infrastructure/skills/knowledge.py apps/api/src/agent/skills/knowledge.py
git mv src/nexoia/infrastructure/skills/core.py     apps/api/src/agent/skills/core.py
```

- [ ] Commit:

```bash
git add -A
git commit -m "chore: move langgraph runtime, prompt, guards, and skills to apps/api/src/agent/"
```

---

## Task 3 — Move shared files

Move domain, infrastructure adapters, config, memory, and application.

- [ ] Move domain subdirectories and top-level files:

```bash
git mv src/nexoia/domain/entities        apps/api/src/shared/domain/entities
git mv src/nexoia/domain/events          apps/api/src/shared/domain/events
git mv src/nexoia/domain/ports           apps/api/src/shared/domain/ports
git mv src/nexoia/domain/value_objects   apps/api/src/shared/domain/value_objects
git mv src/nexoia/domain/errors.py       apps/api/src/shared/domain/errors.py
git mv src/nexoia/domain/policies/communication_rules.py \
       apps/api/src/shared/domain/policies/communication_rules.py
```

- [ ] Move infrastructure adapters (every adapter except `langgraph_runtime`, `skills`, and the `system_prompt.py` already moved):

```bash
git mv src/nexoia/infrastructure/db           apps/api/src/shared/adapters/db
git mv src/nexoia/infrastructure/cademi       apps/api/src/shared/adapters/cademi
git mv src/nexoia/infrastructure/chatnexo     apps/api/src/shared/adapters/chatnexo
git mv src/nexoia/infrastructure/clock        apps/api/src/shared/adapters/clock
git mv src/nexoia/infrastructure/crypto       apps/api/src/shared/adapters/crypto
git mv src/nexoia/infrastructure/hubla        apps/api/src/shared/adapters/hubla
git mv src/nexoia/infrastructure/kb           apps/api/src/shared/adapters/kb
git mv src/nexoia/infrastructure/llm          apps/api/src/shared/adapters/llm
git mv src/nexoia/infrastructure/loja_express apps/api/src/shared/adapters/loja_express
git mv src/nexoia/infrastructure/meta         apps/api/src/shared/adapters/meta
git mv src/nexoia/infrastructure/observability apps/api/src/shared/adapters/observability
git mv src/nexoia/infrastructure/redis        apps/api/src/shared/adapters/redis
```

- [ ] Move config:

```bash
git mv src/nexoia/config apps/api/src/shared/config
```

  > Note: `git mv` moves the directory but the placeholder `__init__.py` created in Task 1 is already gone because git moved the real directory on top of it. That is fine — the real `config/` files take its place.

- [ ] Move memory:

```bash
git mv src/nexoia/application/memory apps/api/src/shared/memory
```

- [ ] Move remaining application files (use_cases, scheduler, handlers, and top-level .py files).  
  Because `application/memory` has already been moved, move the rest of `application/`:

```bash
git mv src/nexoia/application/use_cases           apps/api/src/shared/application/use_cases
git mv src/nexoia/application/scheduler           apps/api/src/shared/application/scheduler
git mv src/nexoia/application/lifecycle_handler.py  apps/api/src/shared/application/lifecycle_handler.py
git mv src/nexoia/application/message_dispatcher.py apps/api/src/shared/application/message_dispatcher.py
git mv src/nexoia/application/purchase_handler.py   apps/api/src/shared/application/purchase_handler.py
```

- [ ] Commit:

```bash
git add -A
git commit -m "chore: move domain, adapters, config, memory, and application to apps/api/src/shared/"
```

---

## Task 4 — Move interface + main/worker

- [ ] Move interface directory:

```bash
git mv src/nexoia/interface apps/api/src/interface
```

- [ ] Move entry-point modules:

```bash
git mv src/nexoia/main.py   apps/api/src/main.py
git mv src/nexoia/worker.py apps/api/src/worker.py
```

- [ ] Commit:

```bash
git add -A
git commit -m "chore: move interface, main.py, and worker.py to apps/api/src/"
```

---

## Task 5 — Move tests, migrations, and root config files

- [ ] Move tests and migrations:

```bash
git mv tests     apps/api/tests
git mv migrations apps/api/migrations
```

- [ ] Move alembic.ini:

```bash
git mv alembic.ini apps/api/alembic.ini
```

- [ ] Copy (not `git mv`) pyproject.toml and Dockerfile — the root copies will be deleted in Task 8 after the modified versions are confirmed good:

```bash
cp pyproject.toml apps/api/pyproject.toml
cp Dockerfile     apps/api/Dockerfile
```

- [ ] Commit:

```bash
git add -A
git commit -m "chore: move tests, migrations, alembic.ini; copy pyproject.toml and Dockerfile to apps/api/"
```

---

## Task 6 — Create `agent/contracts.py` and update config files

### 6a — Create `apps/api/src/agent/contracts.py`

- [ ] Create the file with the following exact content:

```python
# apps/api/src/agent/contracts.py
"""Lightweight result types used across agent skills and use-cases."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Ok:
    """Successful result carrying an optional payload."""

    value: Any = None


@dataclass(frozen=True)
class Err:
    """Failed result carrying a human-readable reason."""

    reason: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Precondition:
    """A guard check result — either passed or blocked with a message."""

    passed: bool
    block_message: str = ""

    @classmethod
    def ok(cls) -> "Precondition":
        return cls(passed=True)

    @classmethod
    def block(cls, message: str) -> "Precondition":
        return cls(passed=False, block_message=message)
```

### 6b — Update `apps/api/pyproject.toml`

- [ ] Change the `[tool.hatch.build.targets.wheel]` section and `testpaths`:

Replace:

```toml
[tool.hatch.build.targets.wheel]
packages = ["src/nexoia"]
```

with:

```toml
[tool.hatch.build.targets.wheel]
packages = [
  {include = "agent",     from = "src"},
  {include = "shared",    from = "src"},
  {include = "interface", from = "src"},
]
```

Replace:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
```

with:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
```

  (no change needed — `testpaths` already says `["tests"]` which is correct relative to `apps/api/`)

Also update the `[tool.ruff]` `src` setting:

Replace:

```toml
src = ["src", "tests"]
```

with:

```toml
src = ["src", "tests"]
```

  (no change needed here either)

The full updated `[tool.hatch.build.targets.wheel]` block in `apps/api/pyproject.toml` should read:

```toml
[tool.hatch.build.targets.wheel]
packages = [
  {include = "agent",     from = "src"},
  {include = "shared",    from = "src"},
  {include = "interface", from = "src"},
]
```

### 6c — Verify `apps/api/alembic.ini`

- [ ] Confirm that `prepend_sys_path = . src` is present (it is, no change needed — paths are relative to the ini file location which is now `apps/api/`).

### 6d — Update `apps/api/Dockerfile`

- [ ] Change the `CMD` line and fix COPY paths (the Dockerfile is now at `apps/api/`, so relative paths must account for the new build context `apps/api/`):

Full updated `apps/api/Dockerfile`:

```dockerfile
# syntax=docker/dockerfile:1.7
FROM python:3.11-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.5 /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src ./src
RUN uv sync --frozen --no-dev

# -----------------------------
FROM python:3.11-slim AS runtime

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/src /app/src
COPY alembic.ini ./
COPY migrations ./migrations

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH="/app/src"

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

  Note: The only line that changes vs. the original is the last `CMD` line (`nexoia.main:app` → `main:app`). The build context will now be `apps/api/` so all relative COPY paths remain valid.

### 6e — Update root `docker-compose.yml`

- [ ] Change the `api` and `worker` service commands, the build context, and the volume mounts:

Full updated `docker-compose.yml`:

```yaml
services:
  postgres:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_USER: nexoia
      POSTGRES_PASSWORD: nexoia
      POSTGRES_DB: nexoia
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U nexoia"]
      interval: 5s
      retries: 10

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      retries: 10

  api:
    build: apps/api
    env_file: .env
    depends_on:
      postgres: { condition: service_healthy }
      redis: { condition: service_healthy }
    ports:
      - "8000:8000"
    command: ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
    volumes:
      - ./apps/api/src:/app/src

  worker:
    build: apps/api
    env_file: .env
    depends_on:
      postgres: { condition: service_healthy }
      redis: { condition: service_healthy }
    command: ["python", "-m", "worker"]
    volumes:
      - ./apps/api/src:/app/src

volumes:
  pgdata:
```

### 6f — Update `scripts/smoke.sh`

- [ ] Update alembic and uvicorn invocations to run from `apps/api/`:

Full updated `scripts/smoke.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

echo "1. Starting services via docker-compose..."
docker compose up -d postgres redis

echo "2. Waiting for services..."
sleep 3

echo "3. Running migrations..."
uv run --directory apps/api alembic upgrade head

echo "4. Starting API in background..."
uv run --directory apps/api uvicorn main:app --port 8000 &
API_PID=$!
trap "kill $API_PID" EXIT
sleep 3

echo "5. Healthcheck..."
curl -f http://localhost:8000/health

echo "6. POST webhook..."
curl -f -X POST http://localhost:8000/webhook/purchase \
  -H "Content-Type: application/json" \
  -H "X-Hubla-Token: ${HUBLA_WEBHOOK_SECRET}" \
  -d '{
    "purchase_id":"smoke-1","account_id":1,"name":"Smoke",
    "email":"s@t.com","phone":"11987654321","product":"X",
    "amount_brl":100,"occurred_at":"2026-04-17T10:00:00Z"
  }'

echo ""
echo "7. Queue depth (should be 1):"
docker compose exec redis redis-cli LLEN "queue:jobs:list"

echo "✓ Smoke done"
```

- [ ] Commit all config file changes:

```bash
git add apps/api/src/agent/contracts.py \
        apps/api/pyproject.toml \
        apps/api/alembic.ini \
        apps/api/Dockerfile \
        docker-compose.yml \
        scripts/smoke.sh
git commit -m "chore: update config files and add agent/contracts.py for new monorepo layout"
```

---

## Task 7 — Write and run the import migration script

### 7a — Create `scripts/migrate_imports.py`

- [ ] Create the file with the following exact content:

```python
#!/usr/bin/env python3
"""Rewrite nexoia.* imports to the new package layout.

Usage:
    python scripts/migrate_imports.py
"""
from __future__ import annotations

import sys
from pathlib import Path

REPLACEMENTS: list[tuple[str, str]] = [
    # Most specific first (guards move to agent, not shared.domain)
    ("from nexoia.domain.policies.guards", "from agent.guards"),
    # LangGraph renames
    ("from nexoia.infrastructure.langgraph_runtime.graph_builder", "from agent.graph"),
    ("from nexoia.infrastructure.langgraph_runtime.nodes", "from agent.react_node"),
    ("from nexoia.infrastructure.langgraph_runtime.state", "from agent.state"),
    ("from nexoia.infrastructure.langgraph_runtime.checkpointer", "from agent.checkpointer"),
    ("from nexoia.infrastructure.langgraph_runtime", "from agent"),
    # Skills stay in agent (flat for now)
    ("from nexoia.infrastructure.skills", "from agent.skills"),
    # system_prompt moves to agent.prompt
    ("from nexoia.infrastructure.llm.system_prompt", "from agent.prompt"),
    # Remaining adapters
    ("from nexoia.infrastructure.db", "from shared.adapters.db"),
    ("from nexoia.infrastructure.observability", "from shared.adapters.observability"),
    ("from nexoia.infrastructure.kb", "from shared.adapters.kb"),
    ("from nexoia.infrastructure.redis", "from shared.adapters.redis"),
    ("from nexoia.infrastructure.llm", "from shared.adapters.llm"),
    ("from nexoia.infrastructure.meta", "from shared.adapters.meta"),
    ("from nexoia.infrastructure.loja_express", "from shared.adapters.loja_express"),
    ("from nexoia.infrastructure.cademi", "from shared.adapters.cademi"),
    ("from nexoia.infrastructure.chatnexo", "from shared.adapters.chatnexo"),
    ("from nexoia.infrastructure.hubla", "from shared.adapters.hubla"),
    ("from nexoia.infrastructure.clock", "from shared.adapters.clock"),
    ("from nexoia.infrastructure.crypto", "from shared.adapters.crypto"),
    # Memory before application (more specific)
    ("from nexoia.application.memory", "from shared.memory"),
    # Application (handlers, use_cases, scheduler)
    ("from nexoia.application", "from shared.application"),
    # Domain (remaining after guards handled above)
    ("from nexoia.domain", "from shared.domain"),
    # Config
    ("from nexoia.config", "from shared.config"),
    # Interface
    ("from nexoia.interface", "from interface"),
    # Main module
    ("from nexoia.main", "from main"),
    ("import nexoia", "import main"),  # fallback
]

SEARCH_ROOTS = [
    Path("apps/api/src"),
    Path("apps/api/tests"),
    Path("apps/api/migrations"),
]


def migrate_file(path: Path) -> bool:
    original = path.read_text(encoding="utf-8")
    text = original
    for old, new in REPLACEMENTS:
        text = text.replace(old, new)
    if text != original:
        path.write_text(text, encoding="utf-8")
        return True
    return False


def main() -> None:
    updated: list[Path] = []
    for root in SEARCH_ROOTS:
        if not root.exists():
            print(f"WARNING: search root not found, skipping: {root}", file=sys.stderr)
            continue
        for py_file in sorted(root.rglob("*.py")):
            if migrate_file(py_file):
                updated.append(py_file)

    for p in updated:
        print(f"  updated: {p}")
    print(f"\nUpdated {len(updated)} files.")


if __name__ == "__main__":
    main()
```

### 7b — Run the script

- [ ] Execute from the repo root:

```bash
python scripts/migrate_imports.py
```

Expected output (exact file count will vary):

```
  updated: apps/api/migrations/env.py
  updated: apps/api/src/agent/checkpointer.py
  updated: apps/api/src/agent/graph.py
  updated: apps/api/src/agent/react_node.py
  updated: apps/api/src/agent/skills/__init__.py
  updated: apps/api/src/agent/skills/access.py
  updated: apps/api/src/agent/skills/knowledge.py
  updated: apps/api/src/agent/skills/refund.py
  ... (more files)

Updated X files.
```

- [ ] Commit:

```bash
git add scripts/migrate_imports.py apps/api/
git commit -m "chore: add import migration script and apply nexoia.* → agent/shared/interface rewrites"
```

---

## Task 8 — Fix `agent/skills/__init__.py`, clean up old directories and root files

### 8a — Update `apps/api/src/agent/skills/__init__.py`

The old `__init__.py` re-exported from `nexoia.infrastructure.skills.*`. After the import migration it will already read:

```python
from agent.skills.access import make_access_skills
from agent.skills.core import make_core_skills
```

That is correct. No further change is needed unless the file still carries `from __future__ import annotations` — keep that line if present.

- [ ] Verify the file looks like this (open it and confirm):

```python
from __future__ import annotations

from agent.skills.access import make_access_skills
from agent.skills.core import make_core_skills

__all__ = ["make_access_skills", "make_core_skills"]
```

### 8b — Remove the now-empty `src/nexoia/` tree

After all `git mv` operations the remaining `src/nexoia/` tree should contain only empty `__init__.py` files and `__pycache__` directories.

- [ ] Remove the stale tree:

```bash
git rm -r src/nexoia/
# Remove any leftover __pycache__ that git does not track:
find src/ -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
# If src/ is now empty, remove it:
rmdir src/ 2>/dev/null || true
```

### 8c — Remove the root `pyproject.toml` and `Dockerfile`

These were copied (not `git mv`'d) in Task 5, so git still tracks them at the repo root. Remove them now that `apps/api/` has the authoritative versions:

```bash
git rm pyproject.toml
git rm Dockerfile
```

### 8d — Commit:

```bash
git add -A
git commit -m "chore: remove legacy src/nexoia/ tree and root pyproject.toml / Dockerfile"
```

---

## Task 9 — Verify tests pass

- [ ] Run unit tests from the `apps/api/` workspace:

```bash
cd apps/api && uv run pytest tests/unit/ -v --tb=short 2>&1 | tail -40
```

Expected output ends with something like:

```
============================================================ short test summary info =============================================================
PASSED tests/unit/test_smoke.py::test_imports
PASSED tests/unit/test_kb_settings.py::...
============================================================ X passed in Y.XXs ============================================================
```

- [ ] If any test fails with an `ImportError` or `ModuleNotFoundError`, the error message will show the exact broken import path. Fix it by either:
  1. Adding the missing rule to `REPLACEMENTS` in `scripts/migrate_imports.py`, re-running the script, and re-running tests; **or**
  2. Editing the file directly if it is an isolated one-off case.

- [ ] Once all unit tests pass, commit any fixes:

```bash
git add -A
git commit -m "fix: correct residual import paths after monorepo restructure"
```

---

## Summary of path changes

| Old path | New path |
|---|---|
| `src/nexoia/infrastructure/langgraph_runtime/graph_builder.py` | `apps/api/src/agent/graph.py` |
| `src/nexoia/infrastructure/langgraph_runtime/nodes.py` | `apps/api/src/agent/react_node.py` |
| `src/nexoia/infrastructure/langgraph_runtime/state.py` | `apps/api/src/agent/state.py` |
| `src/nexoia/infrastructure/langgraph_runtime/checkpointer.py` | `apps/api/src/agent/checkpointer.py` |
| `src/nexoia/infrastructure/llm/system_prompt.py` | `apps/api/src/agent/prompt.py` |
| `src/nexoia/domain/policies/guards/` | `apps/api/src/agent/guards/` |
| `src/nexoia/infrastructure/skills/` | `apps/api/src/agent/skills/` |
| `src/nexoia/domain/` (minus guards) | `apps/api/src/shared/domain/` |
| `src/nexoia/infrastructure/` (minus langgraph_runtime, skills, llm/system_prompt) | `apps/api/src/shared/adapters/` |
| `src/nexoia/config/` | `apps/api/src/shared/config/` |
| `src/nexoia/application/memory/` | `apps/api/src/shared/memory/` |
| `src/nexoia/application/` (minus memory) | `apps/api/src/shared/application/` |
| `src/nexoia/interface/` | `apps/api/src/interface/` |
| `src/nexoia/main.py` | `apps/api/src/main.py` |
| `src/nexoia/worker.py` | `apps/api/src/worker.py` |
| `tests/` | `apps/api/tests/` |
| `migrations/` | `apps/api/migrations/` |
| `alembic.ini` | `apps/api/alembic.ini` |
| `pyproject.toml` | `apps/api/pyproject.toml` (root copy deleted) |
| `Dockerfile` | `apps/api/Dockerfile` (root copy deleted) |
| *(new)* | `apps/api/src/agent/contracts.py` |
