#!/usr/bin/env bash
set -euo pipefail

backup_file="backup_bilibili_$(date +%Y%m%d_%H%M%S).sql"

if [ -z "${BILIBILI_CREDENTIALS_ENCRYPTION_KEY:-}" ]; then
  echo "BILIBILI_CREDENTIALS_ENCRYPTION_KEY is not set. Add it to the deployment environment before continuing." >&2
  exit 1
fi

echo "Backing up database to ${backup_file}..."
docker compose exec -T db pg_dump -U "${POSTGRES_USER:-postgres}" "${POSTGRES_DB:-app}" > "${backup_file}"

echo "Building and starting services..."
docker compose up -d --build --wait backend frontend

echo "Applying migrations..."
docker compose exec backend alembic upgrade head

echo "Initializing permissions and seed data..."
docker compose exec backend python -c "from app.initial_data import init; init()"

echo "Bilibili deployment complete. Assign the appropriate RBAC role to users in /admin/roles."
