# Zero-Downtime Deploy com nginx Blue-Green

**Data:** 2026-05-21
**Status:** Aprovado

---

## Problema

O deploy atual executa `docker compose up -d --force-recreate api worker web`, derrubando e recriando todos os containers simultaneamente. Isso causa downtime visível para os usuários durante cada deploy.

O Cloudflare Tunnel aponta diretamente para `localhost:8000` (api) e `localhost:3000` (web) — sem nenhum proxy intermediário — tornando impossível fazer trocas atômicas com a arquitetura atual.

---

## Solução: nginx no host + Blue-Green Deployment

### Arquitetura

```
Cloudflare Tunnel → localhost:8000 → nginx → api-blue (8001)  OU  api-green (8002)
Cloudflare Tunnel → localhost:3000 → nginx → web-blue (3001)  OU  web-green (3002)
```

O nginx é instalado diretamente no host (não em Docker). O Cloudflare Tunnel não muda — continua apontando para `8000` e `3000`.

O **worker** não participa do blue-green. Ele processa jobs da fila Postgres — uma pausa de 15-30s durante o deploy é aceitável porque os jobs são duráveis e processados assim que o worker volta.

### Fluxo de Deploy

```
1. Ler /root/.deploy-color  →  determina cor ativa (ex: "blue") e nova (ex: "green")
2. docker compose pull        →  baixar novas imagens
3. alembic upgrade heads      →  aplicar migrations (antes de qualquer container novo)
4. docker compose --profile green up -d  →  subir api-green (8002) + web-green (3002)
5. Health check em localhost:8002/health  (max 90s, polling a cada 5s)
6. Se health check falhar: parar green, sair com exit 1 (blue continua servindo)
7. sed upstreams nginx.conf: 8001→8002, 3001→3002
8. nginx -s reload             →  troca atômica (< 1ms, zero requests perdidas)
9. docker compose --profile blue down   →  parar containers antigos
10. docker compose restart worker       →  restart normal do worker
11. Limpeza de imagens antigas (manter últimas 3 por repositório)
12. echo "green" > /root/.deploy-color  →  persistir novo estado
```

### Rollback

Se o health check do green falhar (passo 5-6), o nginx não é tocado — blue continua servindo normalmente. O deploy falha no GitHub Actions sem impacto para o usuário.

Rollback manual a qualquer momento:

```bash
/root/rollback.sh
```

O script lê `.deploy-color`, inverte a cor, atualiza o nginx.conf e faz `nginx -s reload`.

---

## Componentes

### 1. nginx — `/etc/nginx/conf.d/agente-plug.conf`

```nginx
upstream api_backend { server 127.0.0.1:8001; }   # ← 8001 ou 8002
upstream web_backend { server 127.0.0.1:3001; }   # ← 3001 ou 3002

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

O deploy script usa `sed` para trocar os números de porta nos blocos `upstream` antes de fazer `nginx -s reload`.

### 2. `docker-compose.prod.yml` — Profiles Blue/Green

Substitui os serviços `api` e `web` (que expunham as portas 8000/3000) por quatro serviços com profiles:

```yaml
services:
  api-blue:
    profiles: [blue]
    image: ghcr.io/nexo-ia-project/agente-plug-api:${IMAGE_TAG:-latest}
    ports: ["127.0.0.1:8001:8000"]
    restart: unless-stopped
    env_file: /root/.env.prod
    depends_on:
      redis: { condition: service_healthy }
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 10s
      timeout: 5s
      retries: 6
      start_period: 30s

  api-green:
    profiles: [green]
    image: ghcr.io/nexo-ia-project/agente-plug-api:${IMAGE_TAG:-latest}
    ports: ["127.0.0.1:8002:8000"]
    restart: unless-stopped
    env_file: /root/.env.prod
    depends_on:
      redis: { condition: service_healthy }
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 10s
      timeout: 5s
      retries: 6
      start_period: 30s

  web-blue:
    profiles: [blue]
    image: ghcr.io/nexo-ia-project/agente-plug-web:${IMAGE_TAG:-latest}
    ports: ["127.0.0.1:3001:3000"]
    restart: unless-stopped
    env_file: /root/.env.prod
    healthcheck:
      test: ["CMD", "wget", "-q", "-O", "/dev/null", "http://localhost:3000/"]
      interval: 10s
      timeout: 5s
      retries: 6
      start_period: 45s

  web-green:
    profiles: [green]
    image: ghcr.io/nexo-ia-project/agente-plug-web:${IMAGE_TAG:-latest}
    ports: ["127.0.0.1:3002:3000"]
    restart: unless-stopped
    env_file: /root/.env.prod
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

  redis:
    image: redis:7-alpine
    restart: unless-stopped
    command: redis-server --requirepass ${REDIS_PASSWORD} --bind 0.0.0.0
    healthcheck:
      test: ["CMD", "redis-cli", "-a", "${REDIS_PASSWORD}", "ping"]
      interval: 10s
      retries: 5
```

### 3. `scripts/deploy.sh`

Script principal de deploy, versionado no repositório. Chamado pelo GitHub Actions com `IMAGE_TAG` como variável de ambiente.

**Responsabilidades:**
- Ler estado atual (`/root/.deploy-color`)
- Determinar cor nova (inverso da atual)
- Pull de imagens
- Rodar migrations
- Subir containers da cor nova
- Health check com timeout
- Atualizar nginx.conf via `sed`
- `nginx -s reload`
- Parar containers da cor antiga
- Restart do worker
- Limpeza de imagens
- Persistir novo estado

**Variáveis de entrada:** `IMAGE_TAG` (obrigatório)

**Saída:** exit 0 em sucesso, exit 1 em falha (com logs diagnósticos)

### 4. `scripts/rollback.sh`

Script de rollback manual. Lê `/root/.deploy-color`, inverte a cor, atualiza os upstreams do nginx.conf e faz `nginx -s reload`. Não reinicia nenhum container — apenas redireciona o tráfego de volta para a cor anterior (que ainda está rodando, pois o deploy para os containers antigos só acontece após a troca bem-sucedida).

> **Atenção:** rollback só é possível enquanto os containers da cor anterior ainda estiverem rodando. Após o deploy completar e derrubar os containers antigos, rollback requer um novo deploy com a imagem anterior.

### 5. Limpeza de Imagens

Executada ao final de cada deploy (passo 11):

```bash
for repo in agente-plug-api agente-plug-web; do
  docker images "ghcr.io/nexo-ia-project/${repo}" \
    --format "{{.ID}}" | tail -n +4 | xargs -r docker rmi -f
done
docker image prune -f
```

Mantém as **3 imagens mais recentes** por repositório. Remove imagens dangling (sem tag).

### 6. `.github/workflows/deploy.yml` — Step Deploy

```yaml
- name: Deploy
  env:
    IMAGE_TAG: ${{ needs.build-push.outputs.image_tag }}
  run: bash /root/agente-plug/scripts/deploy.sh
```

Remove todo o código inline do step atual e delega para o script versionado.

---

## Setup Inicial no Servidor (one-time)

Antes do primeiro deploy com esta arquitetura, executar manualmente:

```bash
# 1. Instalar nginx
apt-get install -y nginx

# 2. Copiar configuração inicial
cp /root/agente-plug/scripts/nginx-agente-plug.conf /etc/nginx/conf.d/agente-plug.conf
rm /etc/nginx/sites-enabled/default  # remover default se existir

# 3. Testar e iniciar nginx
nginx -t && systemctl enable nginx && systemctl start nginx

# 4. Parar containers atuais (api, web) — downtime único de migração
docker compose --env-file /root/.env.prod -f docker-compose.prod.yml down api web

# 5. Subir containers blue (primeira vez)
IMAGE_TAG=latest docker compose --env-file /root/.env.prod \
  -f docker-compose.prod.yml --profile blue up -d

# 6. Inicializar estado
echo "blue" > /root/.deploy-color

# 7. Verificar
curl http://localhost:8000/health
```

---

## Arquivos Criados/Alterados

| Arquivo | Ação |
|---|---|
| `scripts/deploy.sh` | Novo — script principal blue-green |
| `scripts/rollback.sh` | Novo — rollback manual |
| `scripts/nginx-agente-plug.conf` | Novo — config nginx inicial (blue) |
| `docker-compose.prod.yml` | Atualizado — profiles blue/green, portas separadas |
| `.github/workflows/deploy.yml` | Atualizado — step deploy delega para script |

---

## Invariantes

- Migrations sempre rodam **antes** de qualquer container novo subir
- nginx só é recarregado **depois** do health check da nova cor passar
- Containers da cor antiga só são parados **depois** do nginx recarregar
- O estado `/root/.deploy-color` só é atualizado **ao final** do deploy bem-sucedido
- Em qualquer falha antes do `nginx -s reload`, o ambiente antigo permanece intacto
