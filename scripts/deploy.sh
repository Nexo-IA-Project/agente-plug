#!/usr/bin/env bash
# Blue-green deploy script.
# Requer: IMAGE_TAG (env var), nginx instalado no host, /root/.deploy-color
set -euo pipefail

# ── Configuração ─────────────────────────────────────────────────────────────
REPO_DIR="/root/nexo-flow"
COMPOSE_FILE="${REPO_DIR}/docker-compose.prod.yml"
ENV_FILE="/root/.env.prod"
STATE_FILE="/root/.deploy-color"
NGINX_CONF="/etc/nginx/conf.d/nexo-flow.conf"
IMAGE_API="ghcr.io/nexo-ia-project/nexo-flow-api"
IMAGE_WEB="ghcr.io/nexo-ia-project/nexo-flow-web"

# IMAGE_TAG obrigatório
: "${IMAGE_TAG:?Variável IMAGE_TAG é obrigatória}"
IMAGE_TAG_LC=$(echo "${IMAGE_TAG}" | tr '[:upper:]' '[:lower:]')

# ── Determinar cores ──────────────────────────────────────────────────────────
CURRENT_COLOR=$(cat "${STATE_FILE}" 2>/dev/null || echo "blue")
if [ "${CURRENT_COLOR}" = "blue" ]; then
  NEW_COLOR="green"
  NEW_API_PORT="8002"; NEW_WEB_PORT="3002"
  OLD_API_PORT="8001"; OLD_WEB_PORT="3001"
else
  NEW_COLOR="blue"
  NEW_API_PORT="8001"; NEW_WEB_PORT="3001"
  OLD_API_PORT="8002"; OLD_WEB_PORT="3002"
fi

echo "==> Deploy: ${CURRENT_COLOR} → ${NEW_COLOR} (api:${NEW_API_PORT}, web:${NEW_WEB_PORT})"

# ── Pull imagens ──────────────────────────────────────────────────────────────
echo "==> Baixando imagens..."
docker pull "${IMAGE_API}:${IMAGE_TAG_LC}"
docker pull "${IMAGE_WEB}:${IMAGE_TAG_LC}"

# ── Migrations ────────────────────────────────────────────────────────────────
echo "==> Aplicando migrations..."
docker run --rm \
  --env-file "${ENV_FILE}" \
  --network host \
  "${IMAGE_API}:${IMAGE_TAG_LC}" \
  alembic upgrade heads

# ── Subir containers novos ────────────────────────────────────────────────────
echo "==> Subindo containers ${NEW_COLOR}..."
IMAGE_TAG="${IMAGE_TAG_LC}" docker compose \
  --env-file "${ENV_FILE}" \
  -f "${COMPOSE_FILE}" \
  --profile "${NEW_COLOR}" \
  up -d

# ── Health check api nova cor ─────────────────────────────────────────────────
echo "==> Aguardando api-${NEW_COLOR} ficar healthy (max 90s)..."
for i in $(seq 1 18); do
  if curl -sf --max-time 5 "http://127.0.0.1:${NEW_API_PORT}/health" | grep -q '"ok"'; then
    echo "    api-${NEW_COLOR} healthy!"
    break
  fi
  echo "    [${i}/18] ainda não healthy, aguardando 5s..."
  if [ "${i}" = "18" ]; then
    echo "ERRO: api-${NEW_COLOR} não ficou healthy em 90s"
    docker logs "nexo-flow-api-${NEW_COLOR}-1" --tail=40 2>/dev/null || true
    echo "==> Derrubando ${NEW_COLOR} — ${CURRENT_COLOR} continua servindo."
    IMAGE_TAG="${IMAGE_TAG_LC}" docker compose \
      --env-file "${ENV_FILE}" \
      -f "${COMPOSE_FILE}" \
      --profile "${NEW_COLOR}" \
      down
    exit 1
  fi
  sleep 5
done

# ── Trocar upstream nginx ─────────────────────────────────────────────────────
echo "==> Trocando nginx para ${NEW_COLOR}..."
sudo sed -i "s/server 127.0.0.1:${OLD_API_PORT};/server 127.0.0.1:${NEW_API_PORT};/" "${NGINX_CONF}"
sudo sed -i "s/server 127.0.0.1:${OLD_WEB_PORT};/server 127.0.0.1:${NEW_WEB_PORT};/" "${NGINX_CONF}"
sudo nginx -t
sudo nginx -s reload
echo "    nginx recarregado — tráfego agora em ${NEW_COLOR}"

# ── Parar containers antigos ──────────────────────────────────────────────────
echo "==> Parando containers ${CURRENT_COLOR}..."
IMAGE_TAG="${IMAGE_TAG_LC}" docker compose \
  --env-file "${ENV_FILE}" \
  -f "${COMPOSE_FILE}" \
  --profile "${CURRENT_COLOR}" \
  down

# ── Restart worker ────────────────────────────────────────────────────────────
echo "==> Reiniciando worker..."
IMAGE_TAG="${IMAGE_TAG_LC}" docker compose \
  --env-file "${ENV_FILE}" \
  -f "${COMPOSE_FILE}" \
  up -d --force-recreate worker

# ── Limpeza de imagens antigas ────────────────────────────────────────────────
echo "==> Limpando imagens antigas (mantendo últimas 3)..."
for repo in nexo-flow-api nexo-flow-web; do
  OLD_IDS=$(docker images "ghcr.io/nexo-ia-project/${repo}" \
    --format "{{.ID}}" | tail -n +4)
  if [ -n "${OLD_IDS}" ]; then
    echo "${OLD_IDS}" | xargs docker rmi -f 2>/dev/null || true
  fi
done
docker image prune -f

# ── Persistir estado ──────────────────────────────────────────────────────────
echo "${NEW_COLOR}" > "${STATE_FILE}"
echo "==> Deploy completo! Cor ativa: ${NEW_COLOR}"

# ── Status final ──────────────────────────────────────────────────────────────
docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" ps

# ── Smoke test via Cloudflare Tunnel ─────────────────────────────────────────
echo "==> Smoke test..."
for i in 1 2 3; do
  if curl -sf --max-time 10 https://api-iag2.ianexo.com.br/health | grep -q '"ok"'; then
    echo "    Smoke test passou!"
    exit 0
  fi
  echo "    tentativa ${i}/3 falhou, aguardando 10s..."
  sleep 10
done
echo "AVISO: smoke test não confirmou /health via túnel (pode ser latência DNS)"
