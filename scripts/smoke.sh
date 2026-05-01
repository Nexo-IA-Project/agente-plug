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
