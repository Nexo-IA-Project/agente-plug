# Design: Webhook Simplification + Bearer Token Auth

**Data:** 2026-05-05  
**Escopo:** Simplificação do modelo de entrada, autenticação por Bearer Token gerenciado pelo painel, remoção do LeadLock e remoção do processamento de mídia.

---

## Contexto

O produto passou a ter um serviço externo que antecede esta API. Esse serviço:
- Recebe mensagens brutas do WhatsApp via ChatNexo
- Faz buffer e agrupamento de mensagens picadas do mesmo usuário
- Processa mídia (áudio, imagem, vídeo, documento) e converte para texto
- Entrega para esta API apenas texto, via POST com `Authorization: Bearer <token>`

Com isso, várias responsabilidades que existiam aqui tornam-se redundantes e devem ser removidas.

---

## Mudanças

### 1. Novo modelo de entrada do webhook

**Endpoint:** `POST /webhook/message`  
**Auth:** `Authorization: Bearer <token>`

```python
class IncomingMessagePayload(BaseModel):
    account_id: int
    conversation_id: int
    inbox_id: int            # ID da caixa de entrada
    contact_id: int
    contact_phone: str
    contact_name: str | None = None
    message_id: str          # ID único para dedup (antes: chatnexo_message_id)
    text: str                # texto já processado pelo serviço anterior
    occurred_at: str         # ISO 8601
    metadata: dict = {}      # contexto extra opcional
```

**Removidos:** `media_urls`, `classification_hint`.  
**Renomeado:** `chatnexo_message_id` → `message_id` (neutro em relação ao provider).

---

### 2. Autenticação: Bearer Token global gerenciado pelo painel

O `x-api-key` fixo em env var é substituído por token armazenado no banco, criável/revogável via painel admin.

**Tabela nova: `api_tokens`**

| Campo | Tipo | Descrição |
|---|---|---|
| `id` | UUID PK | Identificador |
| `name` | varchar | Rótulo amigável |
| `token_hash` | varchar | SHA-256 do token bruto |
| `created_at` | timestamptz | Criação |
| `last_used_at` | timestamptz, nullable | Último uso |
| `is_active` | boolean | Pode ser revogado sem deletar |

O token bruto (`nxia_<random 32 bytes hex>`) é exibido apenas uma vez na criação. A API armazena apenas o hash.

**Admin endpoints:**
- `POST /admin/api-tokens` → cria token, retorna uma vez o valor bruto
- `GET /admin/api-tokens` → lista tokens (value mascarado)
- `DELETE /admin/api-tokens/{id}` → revoga (is_active = false)

**Validação no webhook:**
1. Extrai token do header `Authorization: Bearer <token>`
2. Calcula `SHA-256(token)`
3. Busca no banco por `token_hash = hash AND is_active = true`
4. Se não encontrado: 401
5. Atualiza `last_used_at` em background (não bloqueia)

---

### 3. Remoção do LeadLock

- Remove `LeadLock` de `shared/adapters/redis/lead_lock.py`
- Remove uso no worker dispatcher e em qualquer handler
- Cada mensagem processa no seu próprio worker de forma totalmente independente
- O serviço anterior já garante que mensagens do mesmo usuário não chegam simultaneamente em volume problemático

A fila PostgreSQL (`job_queue`) permanece para resiliência (retry, DLQ).

---

### 4. Remoção do processamento de mídia

- Remove `media_urls` de `IncomingMessagePayload`, da entidade `Message` e de `MessageModel`
- Remove `transcribe_audio(audio_bytes: bytes) -> str` do port `LLMPort`
- Remove implementação `transcribe_audio` do adapter `OpenAIClient` (whisper-1)
- Remove qualquer código morto associado (imports, métodos sem uso)

---

## O que NÃO muda

- Fila PostgreSQL + worker assíncrono (resiliência, retry, DLQ)
- Redis dedup por `message_id` (evita processamento duplicado)
- Knowledge Base (RAG com pgvector) — continua igual
- Auth admin JWT (para o painel) — continua igual
- Webhook de compras (Hubla) — não é afetado

---

## Migration Alembic necessária

- Criar tabela `api_tokens`
- Remover coluna `media_urls` de `messages` (se existir)
