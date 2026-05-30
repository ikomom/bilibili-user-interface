# AGENTS.md

## Commands

```sh
# Root
bun run dev              # Frontend dev server (:5173)
bun run dev:backend      # Backend dev server (:8888)
bun run dev:all          # Both concurrently

# Frontend
bun run build            # tsc + Vite build
bun run lint             # Biome (lint + format + unsafe fixes)
bunx playwright test     # E2E tests

# Backend (uv)
uv run fastapi dev app/main.py --port 8888
uv run pytest tests/ -v
uv run ruff check app && uv run ruff format app --check
uv run mypy app
uv run alembic upgrade head
uv run alembic revision --autogenerate -m "desc"
uv run python app/initial_data.py  # Seed superuser
```

## Project Structure

- `backend/app/bilibili/` — Bilibili custom module (router, crud, models, sync_service, scheduler, client, websocket, schemas)
- `frontend/src/components/bilibili/` — Bilibili UI components (8 files)
- `frontend/src/client/` — Auto-generated from OpenAPI schema via `bun run generate-client`
- `frontend/src/types/bilibili.ts` — Shared TS types

## Key Architecture

- **DB ORM**: SQLModel, migrations via Alembic (`backend/app/alembic/`)
- **Auth**: JWT tokens, RBAC permissions (`bilibili:subscription:sync` etc.)
- **Sync**: FastAPI BackgroundTasks + APScheduler for scheduled syncs
- **Real-time logs**: WebSocket at `/api/v1/bilibili/ws/sync-logs/{subscription_id}`
- **Sync cancellation**: In-memory `_cancelled_syncs: set[UUID]` in `router.py`
- **Credential security**: Encrypted via `cryptography` before DB storage

## Important Conventions

- Frontend lint is **Biome** (not ESLint/Prettier). Config: `frontend/biome.json`
- Backend lint is **Ruff** + **mypy** (strict) + **ty**. Config: `backend/pyproject.toml`
- Backend tests: `pytest` with `conftest.py` using `_test`-suffixed PostgreSQL DB (仅保留基础测试，无 bilibili 特定测试)
- Frontend tests: Playwright Chromium-only, 4 CI shards (仅保留基础测试，无 bilibili 特定测试)
- `scripts/prestart.sh` runs migrations + seed data automatically in Docker
- `bilibili-api-python>=16.0.0` for B站 API, `apscheduler` for cron sync jobs
- `POSTGRES_PORT` defaults to **8432** (not 5432)
- TanStack Router: auto code-splitting via `@tanstack/router-plugin/vite`
- Vite proxy: `/backend` → `http://localhost:8888` with WebSocket support
- `frontend/src/client/` is auto-generated — edit the OpenAPI schema, not these files
- `frontend/src/components/ui/` is shadcn/ui generated — use existing patterns

## TypeScript / Sync Status

`SyncStatus` type: `"running" | "success" | "failed" | "cancelled"`
When adding a new status, update ALL of:
- `frontend/src/types/bilibili.ts` — type definition
- `frontend/src/components/bilibili/SyncStatusBadge.tsx` — `statusText` + badge variant
- `frontend/src/components/bilibili/SyncLogDialog.tsx` — `statusText`, `statusVariant`, `statusClassName`
