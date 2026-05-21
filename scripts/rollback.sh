#!/usr/bin/env bash
# Rollback manual: redireciona nginx para a cor anterior sem recriar containers.
# Só funciona enquanto os containers da cor anterior ainda estão rodando
# (ou seja, imediatamente após um deploy bem-sucedido).
set -euo pipefail

STATE_FILE="/root/.deploy-color"
NGINX_CONF="/etc/nginx/conf.d/agente-plug.conf"

CURRENT_COLOR=$(cat "${STATE_FILE}" 2>/dev/null || echo "blue")

if [ "${CURRENT_COLOR}" = "blue" ]; then
  PREV_COLOR="green"
  PREV_API_PORT="8002"; PREV_WEB_PORT="3002"
  CURR_API_PORT="8001"; CURR_WEB_PORT="3001"
else
  PREV_COLOR="blue"
  PREV_API_PORT="8001"; PREV_WEB_PORT="3001"
  CURR_API_PORT="8002"; CURR_WEB_PORT="3002"
fi

# Verificar se containers da cor anterior ainda estão rodando
if ! docker ps --format "{{.Names}}" | grep -q "api-${PREV_COLOR}"; then
  echo "ERRO: containers api-${PREV_COLOR} não encontrados."
  echo "Os containers anteriores já foram parados."
  echo "Para reverter, faça um novo deploy com a imagem anterior."
  exit 1
fi

echo "==> Rollback: ${CURRENT_COLOR} → ${PREV_COLOR}"
sed -i "s/server 127.0.0.1:${CURR_API_PORT};/server 127.0.0.1:${PREV_API_PORT};/" "${NGINX_CONF}"
sed -i "s/server 127.0.0.1:${CURR_WEB_PORT};/server 127.0.0.1:${PREV_WEB_PORT};/" "${NGINX_CONF}"
nginx -t
nginx -s reload
echo "    nginx recarregado — tráfego de volta em ${PREV_COLOR}"

# Nota: não atualiza STATE_FILE de propósito — o próximo deploy vai
# detectar a cor errada e pode ser necessário ajustar manualmente se
# quiser continuar usando rollback como swap.
echo "==> Rollback completo. Verifique: curl http://127.0.0.1:8000/health"
