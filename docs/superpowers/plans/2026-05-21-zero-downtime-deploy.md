# Zero-Downtime Deploy — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Adicionar nginx blue-green no servidor para que deploys futuros não causem downtime, mais limpeza automática de imagens Docker antigas.

**Architecture:** nginx instalado no host (não em Docker) fica entre o Cloudflare Tunnel e os containers. Dois conjuntos de containers (blue: portas 8001/3001, green: 8002/3002) alternados via Docker Compose profiles. O deploy sobe a nova cor, aguarda health check, faz `nginx -s reload` atômico, para a cor antiga.

**Tech Stack:** bash, nginx, Docker Compose profiles, GitHub Actions (self-hosted runner), ghcr.io

---

## Mapa de Arquivos

| Arquivo | Ação | Responsabilidade |
|---|---|---|
| `docker-compose.prod.yml` | Modificar | Trocar serviços `api`/`web` por `api-blue`/`api-green`/`web-blue`/`web-green` com profiles |
| `scripts/nginx-agente-plug.conf` | Criar | Config nginx inicial (upstreams apontando para blue: 8001/3001) |
| `scripts/deploy.sh` | Criar | Script principal blue-green — pull, migrate, up green, health check, nginx reload, down blue, cleanup |
| `scripts/rollback.sh` | Criar | Rollback manual — inverte upstream nginx sem recriar containers |
| `.github/workflows/deploy.yml` | Modificar | Step `Deploy` delega para `scripts/deploy.sh` |

---

## Task 1: Atualizar docker-compose.prod.yml com profiles blue/green

**Files:**
- Modify: `docker-compose.prod.yml`

- [ ] **Step 1: Fazer backup do arquivo atual**

```bash
cp docker-compose.prod.yml docker-compose.prod.yml.bak
```

- [ ] **Step 2: Reescrever docker-compose.prod.yml**

Substituir o conteúdo completo por:

```yaml
services:
  redis:
    image: redis:7-alpine
    restart: unless-stopped
    command: redis-server --requirepass ${REDIS_PASSWORD} --bind 0.0.0.0
    healthcheck:
      test: ["CMD", "redis-cli", "-a", "${REDIS_PASSWORD}", "ping"]
      interval: 10s
      retries: 5

  api-blue:
    profiles: [blue]
    image: ghcr.io/nexo-ia-project/agente-plug-api:${IMAGE_TAG:-latest}
    restart: unless-stopped
    env_file: /root/.env.prod
    depends_on:
      redis: { condition: service_healthy }
    ports:
      - "127.0.0.1:8001:8000"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 10s
      timeout: 5s
      retries: 6
      start_period: 30s

  api-green:
    profiles: [green]
    image: ghcr.io/nexo-ia-project/agente-plug-api:${IMAGE_TAG:-latest}
    restart: unless-stopped
    env_file: /root/.env.prod
    depends_on:
      redis: { condition: service_healthy }
    ports:
      - "127.0.0.1:8002:8000"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 10s
      timeout: 5s
      retries: 6
      start_period: 30s

  web-blue:
    profiles: [blue]
    image: ghcr.io/nexo-ia-project/agente-plug-web:${IMAGE_TAG:-latest}
    restart: unless-stopped
    env_file: /root/.env.prod
    ports:
      - "127.0.0.1:3001:3000"
    healthcheck:
      test: ["CMD", "wget", "-q", "-O", "/dev/null", "http://localhost:3000/"]
      interval: 10s
      timeout: 5s
      retries: 6
      start_period: 45s

  web-green:
    profiles: [green]
    image: ghcr.io/nexo-ia-project/agente-plug-web:${IMAGE_TAG:-latest}
    restart: unless-stopped
    env_file: /root/.env.prod
    ports:
      - "127.0.0.1:3002:3000"
    healthcheck:
      test: ["CMD", "wget", "-q", "-O", "/dev/null", "http://localhost:3000/"]
      interval: 10s
      timeout: 5s
      retries: 6
      start_period: 45s

  worker:
    image: ghcr.io/nexo-ia-project/agente-plug-api:${IMAGE_TAG:-latest}
    restart: unless-stopped
    env_file: /root/.env.prod
    depends_on:
      redis: { condition: service_healthy }
    command: ["python", "-m", "worker"]
```

- [ ] **Step 3: Validar sintaxe**

```bash
# Requer IMAGE_TAG e REDIS_PASSWORD definidos para validar
IMAGE_TAG=latest REDIS_PASSWORD=test docker compose -f docker-compose.prod.yml config --quiet
echo "Exit code: $?"
```

Esperado: exit code 0, sem erros.

- [ ] **Step 4: Commit**

```bash
git add docker-compose.prod.yml
git commit -m "feat(deploy): docker-compose.prod.yml com profiles blue/green"
```

---

## Task 2: Criar scripts/nginx-agente-plug.conf

**Files:**
- Create: `scripts/nginx-agente-plug.conf`

- [ ] **Step 1: Criar diretório scripts se não existir**

```bash
mkdir -p scripts
```

- [ ] **Step 2: Criar scripts/nginx-agente-plug.conf**

```nginx
upstream api_backend { server 127.0.0.1:8001; }
upstream web_backend { server 127.0.0.1:3001; }

server {
    listen 8000;
    location / {
        proxy_pass         http://api_backend;
        proxy_http_version 1.1;
        proxy_set_header   Connection "";
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_read_timeout 120s;
    }
}

server {
    listen 3000;
    location / {
        proxy_pass         http://web_backend;
        proxy_http_version 1.1;
        proxy_set_header   Connection "";
        proxy_set_header   Host $host;
    }
}
```

> As portas nos blocos `upstream` são editadas pelo `deploy.sh` via `sed` a cada deploy. A config inicial aponta para `blue` (8001/3001).

- [ ] **Step 3: Commit**

```bash
git add scripts/nginx-agente-plug.conf
git commit -m "feat(deploy): config nginx inicial (upstream blue 8001/3001)"
```

---

## Task 3: Criar scripts/deploy.sh

**Files:**
- Create: `scripts/deploy.sh`

- [ ] **Step 1: Criar scripts/deploy.sh**

```bash
#!/usr/bin/env bash
# Blue-green deploy script.
# Requer: IMAGE_TAG (env var), nginx instalado no host, /root/.deploy-color
set -euo pipefail

# ── Configuração ─────────────────────────────────────────────────────────────
REPO_DIR="/root/agente-plug"
COMPOSE_FILE="${REPO_DIR}/docker-compose.prod.yml"
ENV_FILE="/root/.env.prod"
STATE_FILE="/root/.deploy-color"
NGINX_CONF="/etc/nginx/conf.d/agente-plug.conf"
IMAGE_API="ghcr.io/nexo-ia-project/agente-plug-api"
IMAGE_WEB="ghcr.io/nexo-ia-project/agente-plug-web"

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
    docker logs "agente-plug-api-${NEW_COLOR}-1" --tail=40 2>/dev/null || true
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
sed -i "s/server 127.0.0.1:${OLD_API_PORT};/server 127.0.0.1:${NEW_API_PORT};/" "${NGINX_CONF}"
sed -i "s/server 127.0.0.1:${OLD_WEB_PORT};/server 127.0.0.1:${NEW_WEB_PORT};/" "${NGINX_CONF}"
nginx -t
nginx -s reload
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
for repo in agente-plug-api agente-plug-web; do
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
  if curl -sf --max-time 10 https://api-flow.ianexo.com.br/health | grep -q '"ok"'; then
    echo "    Smoke test passou!"
    exit 0
  fi
  echo "    tentativa ${i}/3 falhou, aguardando 10s..."
  sleep 10
done
echo "AVISO: smoke test não confirmou /health via túnel (pode ser latência DNS)"
```

- [ ] **Step 2: Tornar executável**

```bash
chmod +x scripts/deploy.sh
```

- [ ] **Step 3: Verificar sintaxe bash**

```bash
bash -n scripts/deploy.sh
echo "Exit code: $?"
```

Esperado: exit code 0, sem output de erro.

- [ ] **Step 4: Commit**

```bash
git add scripts/deploy.sh
git commit -m "feat(deploy): script blue-green deploy com health check e limpeza de imagens"
```

---

## Task 4: Criar scripts/rollback.sh

**Files:**
- Create: `scripts/rollback.sh`

- [ ] **Step 1: Criar scripts/rollback.sh**

```bash
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
```

- [ ] **Step 2: Tornar executável e verificar sintaxe**

```bash
chmod +x scripts/rollback.sh
bash -n scripts/rollback.sh
echo "Exit code: $?"
```

Esperado: exit code 0.

- [ ] **Step 3: Commit**

```bash
git add scripts/rollback.sh
git commit -m "feat(deploy): script de rollback manual blue-green"
```

---

## Task 5: Atualizar .github/workflows/deploy.yml

**Files:**
- Modify: `.github/workflows/deploy.yml`

- [ ] **Step 1: Substituir o step `Deploy` no workflow**

Localizar o step `Deploy` dentro do job `deploy` (começa em `- name: Deploy`) e substituir **todo o seu conteúdo** por:

```yaml
      - name: Deploy
        env:
          IMAGE_TAG: ${{ needs.build-push.outputs.image_tag }}
        run: |
          set -euo pipefail
          cd /root/agente-plug
          git pull --ff-only
          IMAGE_TAG="${IMAGE_TAG}" bash scripts/deploy.sh
```

> O step de `Log in to GHCR` antes do Deploy permanece igual — é necessário para o `docker pull` dentro do script.

- [ ] **Step 2: Verificar que o workflow é YAML válido**

```bash
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/deploy.yml'))"
echo "YAML válido"
```

Esperado: `YAML válido`

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/deploy.yml
git commit -m "feat(deploy): workflow delega deploy para scripts/deploy.sh"
```

---

## Task 6: Setup único no servidor (executar manualmente via SSH)

> Este task é executado **uma única vez** no servidor via SSH. Não é automatizável pelo CI porque envolve parar os containers atuais (downtime único de migração ~30s).

**Files:** arquivos no servidor em `/root/agente-plug/` e `/etc/nginx/`

- [ ] **Step 1: Conectar ao servidor**

```bash
ssh root@100.70.85.81
```

- [ ] **Step 2: Garantir que o repositório está no commit com os novos scripts**

```bash
cd /root/agente-plug
git pull --ff-only
ls scripts/deploy.sh scripts/rollback.sh scripts/nginx-agente-plug.conf
```

Esperado: os 3 arquivos listados sem erro.

- [ ] **Step 3: Instalar nginx**

```bash
apt-get update -qq && apt-get install -y nginx
```

- [ ] **Step 4: Copiar config nginx e remover default**

```bash
cp /root/agente-plug/scripts/nginx-agente-plug.conf /etc/nginx/conf.d/agente-plug.conf
# Remover config default do nginx se existir
rm -f /etc/nginx/sites-enabled/default
nginx -t
```

Esperado: `nginx: configuration file /etc/nginx/nginx.conf test is successful`

- [ ] **Step 5: Iniciar nginx**

```bash
systemctl enable nginx
systemctl start nginx
curl -s http://127.0.0.1:8000/
```

Esperado: nginx responde (provavelmente 502 Bad Gateway porque ainda não há containers nas portas 8001/3001 — isso é esperado).

- [ ] **Step 6: Parar containers api e web atuais (downtime ~30s)**

```bash
# Verificar containers rodando antes
docker compose --env-file /root/.env.prod -f docker-compose.prod.yml ps

# Parar api e web (worker e redis continuam)
docker compose --env-file /root/.env.prod -f docker-compose.prod.yml stop api web
docker compose --env-file /root/.env.prod -f docker-compose.prod.yml rm -f api web
```

- [ ] **Step 7: Subir containers blue**

```bash
# Usar a tag da imagem atual (latest ou sha do último deploy)
CURRENT_TAG=$(docker images ghcr.io/nexo-ia-project/agente-plug-api \
  --format "{{.Tag}}" | grep -v latest | head -1 || echo "latest")

echo "Usando tag: ${CURRENT_TAG}"

IMAGE_TAG="${CURRENT_TAG}" docker compose \
  --env-file /root/.env.prod \
  -f docker-compose.prod.yml \
  --profile blue \
  up -d
```

- [ ] **Step 8: Verificar health dos containers blue**

```bash
# Aguardar ~30s para start_period
sleep 35
curl -sf http://127.0.0.1:8001/health | grep '"ok"'
echo "api-blue OK"
curl -sf http://127.0.0.1:8000/health | grep '"ok"'
echo "nginx → api-blue OK"
```

Esperado: ambos retornam `{"status":"ok"}`.

- [ ] **Step 9: Inicializar arquivo de estado**

```bash
echo "blue" > /root/.deploy-color
cat /root/.deploy-color
```

Esperado: `blue`

- [ ] **Step 10: Copiar rollback.sh para /root (atalho conveniente)**

```bash
cp /root/agente-plug/scripts/rollback.sh /root/rollback.sh
chmod +x /root/rollback.sh
```

- [ ] **Step 11: Verificar smoke test final**

```bash
curl -sf https://api-flow.ianexo.com.br/health | grep '"ok"'
echo "Smoke test OK"
```

Esperado: `{"status":"ok"}`

---

## Task 7: Push e validação do primeiro deploy automatizado

**Files:** nenhum arquivo novo — validação end-to-end

- [ ] **Step 1: Push do branch para disparar CI**

```bash
# No repositório local (não no servidor)
git push origin merge/dynamic-followup-meta-templates
```

- [ ] **Step 2: Aguardar CI passar e merge do PR**

Abrir o PR #25 no GitHub e fazer merge após todos os checks passarem. O merge em `main` dispara o job `deploy`.

- [ ] **Step 3: Acompanhar o deploy no GitHub Actions**

```bash
gh run watch --repo Nexo-IA-Project/agente-plug
```

Observar os logs do step `Deploy`. Esperado ver:
```
==> Deploy: blue → green (api:8002, web:3002)
==> Baixando imagens...
==> Aplicando migrations...
==> Subindo containers green...
==> Aguardando api-green ficar healthy...
    api-green healthy!
==> Trocando nginx para green...
    nginx recarregado — tráfego agora em green
==> Parando containers blue...
==> Reiniciando worker...
==> Limpando imagens antigas...
==> Deploy completo! Cor ativa: green
==> Smoke test...
    Smoke test passou!
```

- [ ] **Step 4: Verificar no servidor**

```bash
ssh root@100.70.85.81 "cat /root/.deploy-color && docker ps --format 'table {{.Names}}\t{{.Status}}'"
```

Esperado:
```
green
agente-plug-api-green-1    Up X minutes (healthy)
agente-plug-web-green-1    Up X minutes (healthy)
agente-plug-worker-1       Up X minutes
agente-plug-redis-1        Up X days (healthy)
```

- [ ] **Step 5: Testar rollback manual**

```bash
ssh root@100.70.85.81 "/root/rollback.sh"
# Verificar que voltou para blue
curl -sf https://api-flow.ianexo.com.br/health | grep '"ok"'
```

Esperado: `rollback completo` nos logs e API respondendo.

- [ ] **Step 6: Restaurar para green (fazer deploy novamente ou rodar rollback de volta)**

```bash
# Inverter manualmente de volta para green se quiser manter o último deploy
ssh root@100.70.85.81 "
  sed -i 's/server 127.0.0.1:8001;/server 127.0.0.1:8002;/' /etc/nginx/conf.d/agente-plug.conf
  sed -i 's/server 127.0.0.1:3001;/server 127.0.0.1:3002;/' /etc/nginx/conf.d/agente-plug.conf
  nginx -s reload
  echo 'green' > /root/.deploy-color
  echo 'Restaurado para green'
"
```

---

## Checklist de Self-Review

- [x] Task 1 cobre docker-compose.prod.yml com profiles
- [x] Task 2 cobre nginx config com upstreams blue
- [x] Task 3 cobre deploy.sh completo com health check, sed, reload, cleanup
- [x] Task 4 cobre rollback.sh com verificação de containers vivos
- [x] Task 5 cobre atualização do workflow
- [x] Task 6 cobre setup único no servidor (downtime controlado)
- [x] Task 7 cobre validação end-to-end
- [x] Portas consistentes: blue=8001/3001, green=8002/3002 em todos os tasks
- [x] IMAGE_TAG_LC (lowercase) usado em todos os docker commands
- [x] Migrations rodam antes de qualquer container novo em Task 3
- [x] Fallback (down green se health falhar) documentado em Task 3
