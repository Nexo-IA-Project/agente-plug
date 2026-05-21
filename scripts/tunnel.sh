#!/usr/bin/env bash
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WEB_ENV="$REPO_ROOT/apps/web/.env.local"

# ── Encerra processos anteriores desta aplicação ────────────────────────────
echo "Encerrando tunnels e Next.js anteriores..."
pgrep -f "cloudflared tunnel --url http://localhost:8000" | xargs kill 2>/dev/null || true
pgrep -f "cloudflared tunnel --url http://localhost:3001" | xargs kill 2>/dev/null || true
pgrep -f "next dev.*--port 3001"                         | xargs kill 2>/dev/null || true
sleep 1

cleanup() {
  echo ""
  echo "Encerrando..."
  pgrep -f "cloudflared tunnel --url http://localhost:8000" | xargs kill 2>/dev/null || true
  pgrep -f "cloudflared tunnel --url http://localhost:3001" | xargs kill 2>/dev/null || true
  pgrep -f "next dev.*--port 3001"                         | xargs kill 2>/dev/null || true
  # Restaura NEXT_PUBLIC_API_URL para localhost
  sed -i 's|^NEXT_PUBLIC_API_URL=.*|NEXT_PUBLIC_API_URL=http://localhost:8000|' "$WEB_ENV"
  exit 0
}
trap cleanup INT TERM

# ── Inicia tunnel da API ─────────────────────────────────────────────────────
LOG_API=$(mktemp /tmp/tunnel-api-XXXX.log)
cloudflared tunnel --url http://localhost:8000 >"$LOG_API" 2>&1 &

echo "Aguardando URL do tunnel da API..."
URL_API=""
for _ in $(seq 1 30); do
  URL_API=$(grep -oP 'https://[a-z0-9\-]+\.trycloudflare\.com' "$LOG_API" 2>/dev/null | head -1) || true
  [ -n "$URL_API" ] && break
  sleep 1
done

if [ -z "$URL_API" ]; then
  echo "ERRO: tunnel da API não detectado."
  rm -f "$LOG_API"
  exit 1
fi

echo "API tunnel: $URL_API"

# ── Atualiza NEXT_PUBLIC_API_URL e reinicia Next.js ──────────────────────────
sed -i "s|^NEXT_PUBLIC_API_URL=.*|NEXT_PUBLIC_API_URL=$URL_API|" "$WEB_ENV"
echo "NEXT_PUBLIC_API_URL atualizado → $URL_API"

cd "$REPO_ROOT/apps/web"
npm run dev >/tmp/nextjs-3001.log 2>&1 &

echo "Aguardando Next.js na porta 3001..."
for _ in $(seq 1 30); do
  grep -q "Ready" /tmp/nextjs-3001.log 2>/dev/null && break || true
  sleep 1
done

# ── Inicia tunnel do frontend ────────────────────────────────────────────────
LOG_WEB=$(mktemp /tmp/tunnel-web-XXXX.log)
cloudflared tunnel --url http://localhost:3001 >"$LOG_WEB" 2>&1 &

echo "Aguardando URL do tunnel do frontend..."
URL_WEB=""
for _ in $(seq 1 30); do
  URL_WEB=$(grep -oP 'https://[a-z0-9\-]+\.trycloudflare\.com' "$LOG_WEB" 2>/dev/null | head -1) || true
  [ -n "$URL_WEB" ] && break
  sleep 1
done

echo ""
echo "=================================="
echo " API   (8000): ${URL_API}"
echo " FRONT (3001): ${URL_WEB:-não detectada}"
echo "=================================="
echo ""
echo " Webhook → ${URL_API}/webhook/message"
echo ""
echo "Pressione Ctrl+C para encerrar."

rm -f "$LOG_API" "$LOG_WEB"
wait
