# nexoia-agent

Backend Python da NexoIA — agente de suporte multi-tenant integrado ao ChatNexo.

## Stack
Python 3.11+ · FastAPI · LangGraph · PostgreSQL · Redis · uv · ruff

## Quickstart dev

```bash
uv sync
cp .env.example .env  # preenche as variáveis
uv run alembic upgrade head
uv run uvicorn nexoia.main:app --reload
```

## Testes

```bash
uv run pytest                    # tudo
uv run pytest tests/unit         # só unit
uv run pytest -k "idle"          # filtro
uv run pytest --cov=nexoia       # com coverage
```

Ver `docs/superpowers/specs/2026-04-17-nexoia-agent-core-design.md` para o spec completo.
