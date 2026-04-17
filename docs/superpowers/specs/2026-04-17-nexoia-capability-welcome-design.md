# Spec ② — Capability Welcome

**Data:** 2026-04-17
**Fase:** 1
**Repositório alvo:** `nexoia-agent`
**Depende de:** Spec ① (Core)
**Status:** Design aprovado — aguardando plano de implementação

---

## 1. Contexto e Objetivo

A Capability Welcome é o primeiro ponto de contato da NexoIA com o aluno após uma compra confirmada na Hubla. Ela transforma um evento de compra em uma mensagem de boas-vindas personalizada no WhatsApp, incluindo o link nominal de auto-login da plataforma Cademi.

**Resumo do fluxo:**
```
Hubla (compra confirmada)
  → POST /webhook/purchase (Core já recebe e enfileira)
    → Worker consome job ProcessPurchaseWebhook
      → Invoca subgraph Welcome
        → Busca link na Cademi API
          → Verifica/cria conversa no ChatNexo
            → Envia template welcome_purchase via Meta
              → Agenda D+1 se objetivo não atingido
```

**Nota de arquitetura:** existe um serviço upstream (antes do agente) que faz buffer e concatenação de mensagens. Quando o job chega ao agente, o processamento pode ser imediato — sem delay artificial. O agente tem a variável `MESSAGE_BUFFER_WAIT_SECONDS=0` para uso futuro se necessário.

---

## 2. Escopo

### O que a Capability Welcome FAZ

- Subgraph LangGraph plugado no main graph do Core, acionado pelo job `ProcessPurchaseWebhook`
- Busca dados do aluno na Cademi API (link nominal de auto-login) com retry 3x backoff
- Verifica conversa ativa no ChatNexo — reutiliza se aberta, cria nova se fechada/inexistente
- Envia template `welcome_purchase` via ChatNexo Action API
- Registra `AccessCase` com status `LINK_SENT`
- Agenda `access_reminder_d1` (D+1) na tabela `scheduled_jobs` — dispara se objetivo não atingido
- Cancela o D+1 quando `access_confirmed = True`
- Escala silenciosamente para humano se Cademi falhar após 3 tentativas

### O que NÃO FAZ

- Não processa a resposta do aluno (fluxo reativo — responsabilidade do Intent Router + Core)
- Não implementa o `CademiClient` real — stub com TODO explícito
- Não define o template `welcome_purchase` final — ver OPEN_QUESTIONS.md
- Não gerencia acesso manual, reembolso ou Loja Express → specs ③–⑤

---

## 3. Arquivos

### Novos
```
src/nexoia/application/capabilities/welcome.py      # subgraph + lógica
src/nexoia/domain/entities/access_case.py           # entidade AccessCase
src/nexoia/domain/ports/cademi_port.py              # interface CademiPort
src/nexoia/infrastructure/cademi/client.py          # stub CademiClient
src/nexoia/infrastructure/cademi/schemas.py         # Pydantic schemas Cademi
src/nexoia/infrastructure/db/repositories/access_case_repo.py
migrations/xxxx_add_access_cases_table.py           # Alembic
tests/unit/capabilities/test_welcome.py
tests/integration/test_welcome_flow.py
```

### Modificados
```
src/nexoia/domain/ports/chatnexo_port.py   # + get_open_conversation, create_conversation
src/nexoia/infrastructure/chatnexo/client.py  # implementação dos novos métodos
src/nexoia/interface/worker/handlers/      # + handle_process_purchase_webhook.py
src/nexoia/config/settings.py              # + MESSAGE_BUFFER_WAIT_SECONDS, CADEMI_API_URL, CADEMI_API_KEY
docs/README.md                             # regras de negócio da Capability Welcome
docs/superpowers/OPEN_QUESTIONS.md        # dúvidas pendentes
```

---

## 4. Subgraph LangGraph

### Grafo de nós

```
START
  │
  ▼
fetch_cademi          ← busca CademiStudent por email; retry 3x backoff
  │
  ▼
check_conversation    ← get_open_conversation → reutiliza ou cria_nova
  │
  ▼
send_welcome          ← envia template welcome_purchase via ChatNexo
  │
  ▼
persist_access_case   ← salva AccessCase(status=LINK_SENT) no PostgreSQL
  │
  ▼
schedule_d1           ← insere scheduled_job D+1 em scheduled_jobs
  │
  ▼
END
```

### Estado do subgraph

```python
class WelcomeState(ConversationState):
    purchase_id: str
    student_name: str
    student_phone: str
    student_email: str
    product_name: str
    access_link: str | None        # None se Cademi falhar
    cademi_attempts: int           # contador de retries (máx 3)
    conversation_id: str | None    # ChatNexo conversation_id
    access_case_id: str | None
    access_confirmed: bool         # True = objetivo atingido, cancela D+1
    cademi_failed: bool            # True = seguir com fallback genérico
```

### Nó `fetch_cademi`

1. Chama `CademiPort.get_student_by_email(email)`
2. Se `CademiError` e `cademi_attempts < 3`: incrementa counter, aguarda backoff (`1s * 3^attempt`), retenta
3. Se esgotado: `cademi_failed=True`, `access_link=None`, dispara handoff silencioso para humano

### Nó `check_conversation`

1. Chama `ChatNexoPort.get_open_conversation(account_id, contact_phone)`
2. Se retorna `conversation_id` → usa a conversa existente
3. Se `None` (fechada ou inexistente) → chama `ChatNexoPort.create_conversation(account_id, contact_phone)`

### Nó `send_welcome`

- Se `cademi_failed=False`: envia template com `{{3}} = access_link`
- Se `cademi_failed=True`: envia template com `{{3}} = "em instantes você receberá seu link de acesso"`

> **TODO — ver OPEN_QUESTIONS.md:** Template ID, variáveis exatas e formato do link nominal a confirmar com equipe.

### Nó `schedule_d1`

- Insere `scheduled_jobs` com `run_at = created_at + 1h`, `job_type = SendScheduledFollowUp`, `payload = {template: "access_reminder_d1", access_case_id}`
- Salva `scheduled_d1_job_id` no `AccessCase`

### Cancelamento do D+1

Quando o Intent Router detecta `intent = access_confirmed` na resposta do aluno:
- `scheduler.cancel(access_case.scheduled_d1_job_id)`
- `access_case.status = ACCESSED`
- `access_case.access_confirmed = True`

O D+1 **não** é cancelado apenas pela resposta do aluno — somente quando o objetivo (acesso confirmado) é atingido.

---

## 5. Entidade e Modelo de Dados

### `AccessCase` (`domain/entities/access_case.py`)

```python
@dataclass
class AccessCase:
    id: str                          # UUID
    account_id: int                  # multi-tenancy
    contact_id: str                  # ChatNexo contact_id
    conversation_id: str             # ChatNexo conversation_id
    purchase_id: str                 # idempotência — vem da Hubla
    product_name: str
    access_link: str | None
    status: AccessCaseStatus
    access_confirmed: bool
    scheduled_d1_job_id: str | None  # referência ao scheduled_job
    created_at: datetime
    updated_at: datetime
```

### `AccessCaseStatus`

```python
class AccessCaseStatus(str, Enum):
    PENDING          = "pending"
    LINK_SENT        = "link_sent_proativo"
    ACCESSED         = "accessed"
    REMINDED_D1      = "reminded_d1"
    ESCALATED        = "escalated"       # Cademi falhou 3x
```

### Tabela `access_cases`

```sql
CREATE TABLE access_cases (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id          INTEGER NOT NULL,
    contact_id          TEXT NOT NULL,
    conversation_id     TEXT NOT NULL,
    purchase_id         TEXT NOT NULL UNIQUE,   -- idempotência
    product_name        TEXT NOT NULL,
    access_link         TEXT,
    status              TEXT NOT NULL DEFAULT 'pending',
    access_confirmed    BOOLEAN NOT NULL DEFAULT FALSE,
    scheduled_d1_job_id TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_access_cases_account_contact ON access_cases(account_id, contact_id);
CREATE INDEX idx_access_cases_purchase_id ON access_cases(purchase_id);
```

---

## 6. Ports e Adapters

### `CademiPort` (`domain/ports/cademi_port.py`)

```python
class CademiPort(Protocol):
    async def get_student_by_email(self, email: str) -> CademiStudent | None: ...
    async def get_student_by_cpf(self, cpf: str) -> CademiStudent | None: ...
    async def get_access_link(self, student_id: str, product_id: str) -> str: ...
```

### `CademiStudent` (value object)

```python
@dataclass(frozen=True)
class CademiStudent:
    id: str
    name: str
    email: str
    phone: str | None
```

### `CademiClient` (stub)

```python
# ⚠️  TODO: implementar com documentação real da Cademi API
# ANTES DE IMPLEMENTAR: consultar OPEN_QUESTIONS.md e obter:
#   - Endpoint base da Cademi API
#   - Mecanismo de autenticação
#   - Endpoint para busca de aluno por email/CPF
#   - Endpoint para geração de link nominal de auto-login
#   - Prazo de expiração do link (se houver)
class CademiClient:
    async def get_student_by_email(self, email: str) -> CademiStudent | None:
        raise NotImplementedError("CademiClient não implementado — ver OPEN_QUESTIONS.md")

    async def get_student_by_cpf(self, cpf: str) -> CademiStudent | None:
        raise NotImplementedError("CademiClient não implementado — ver OPEN_QUESTIONS.md")

    async def get_access_link(self, student_id: str, product_id: str) -> str:
        raise NotImplementedError("CademiClient não implementado — ver OPEN_QUESTIONS.md")
```

### Adições ao `ChatNexoPort`

```python
# Novos métodos adicionados ao Port existente do Core
async def get_open_conversation(self, account_id: int, contact_phone: str) -> str | None: ...
async def create_conversation(self, account_id: int, contact_phone: str) -> str: ...
```

---

## 7. Configuração

Variáveis novas em `settings.py`:

```python
# Cademi
CADEMI_API_URL: str = ""         # TODO: preencher com URL real
CADEMI_API_KEY: str = ""         # TODO: preencher com chave real

# Buffer de mensagens (serviço upstream faz o buffer antes de chegar ao agente)
MESSAGE_BUFFER_WAIT_SECONDS: int = 0   # 0 = desativado; ajustar se necessário

# Welcome Capability
WELCOME_D1_DELAY_HOURS: int = 1        # horas para agendar o D+1
CADEMI_MAX_RETRIES: int = 3
CADEMI_RETRY_BASE_SECONDS: float = 1.0  # backoff: 1s, 3s, 9s
```

---

## 8. Observabilidade

### Logs estruturados (structlog)

Cada nó loga: `capability=welcome`, `node`, `purchase_id`, `account_id`, `status`

- Falha Cademi → `level=WARNING`, `attempt`, `error`
- Retry esgotado → `level=WARNING`, `reason=cademi_exhausted`, handoff disparado
- Template enviado → `level=INFO`, `conversation_id`, `template=welcome_purchase`
- D+1 agendado → `level=INFO`, `scheduled_job_id`, `run_at`

### Métricas Prometheus

```
welcome_capability_total{status="success"|"cademi_failed"|"error"}
welcome_cademi_latency_seconds (histogram)
welcome_d1_scheduled_total
welcome_d1_cancelled_total
```

---

## 9. Testes

### Unitários (`tests/unit/capabilities/test_welcome.py`)

| Teste | Cenário |
|-------|---------|
| `test_happy_path` | Cademi retorna link, template enviado, D+1 agendado |
| `test_cademi_retry_exhausted` | 3 falhas → `cademi_failed=True`, boas-vindas genérica, handoff |
| `test_open_conversation_reused` | Conversa aberta → usa existente |
| `test_closed_conversation_creates_new` | Conversa fechada → cria nova |
| `test_d1_cancelled_when_access_confirmed` | `access_confirmed=True` → job cancelado |
| `test_d1_not_cancelled_on_reply_without_confirmation` | Resposta sem confirmação → D+1 mantido |

### Integração (`tests/integration/test_welcome_flow.py`)

- `FakeCademiClient` e `FakeChatNexoClient` como adapters de teste
- Valida `AccessCase` persistido corretamente no PostgreSQL (testcontainers)
- Valida entrada em `scheduled_jobs` após fluxo completo
- Valida cancelamento do D+1 quando `access_confirmed=True`

---

## 10. Requisitos Funcionais

| ID | Requisito |
|----|-----------|
| `RF-W01` | Agente processa o job imediatamente ao receber (sem buffer interno — upstream já faz isso). `MESSAGE_BUFFER_WAIT_SECONDS=0` configurável. |
| `RF-W02` | Retry Cademi: 3x com backoff exponencial (1s, 3s, 9s). Se esgotado: boas-vindas genérica + handoff silencioso. |
| `RF-W03` | Conversa aberta no ChatNexo → reutiliza. Fechada/inexistente → cria nova via API. |
| `RF-W04` | D+1 agendado em `scheduled_jobs` com `run_at = now + WELCOME_D1_DELAY_HOURS`. |
| `RF-W05` | D+1 cancelado quando `access_confirmed = True` (objetivo atingido). |
| `RF-W06` | Template `welcome_purchase`: ID e variáveis exatas a confirmar — ver `OPEN_QUESTIONS.md`. |
| `RF-W07` | Link Cademi — prazo de expiração a confirmar — ver `OPEN_QUESTIONS.md`. |
| `RF-W08` | `AccessCase` persistido com `purchase_id UNIQUE` para idempotência. |
| `RF-W09` | Se email de compra diferir do email Cademi: escalar para humano (não reenviar automaticamente). |

## 11. Requisitos Não-Funcionais

| ID | Requisito |
|----|-----------|
| `RNF-W01` | Tenant isolation: toda query filtra por `account_id`. |
| `RNF-W02` | Idempotência: `purchase_id UNIQUE` garante que webhook duplicado não dispara dois welcomes. |
| `RNF-W03` | Graceful degradation: falha na Cademi não bloqueia envio da boas-vindas. |
| `RNF-W04` | Circuit breaker herdado do Core aplicado ao `CademiClient`. |
| `RNF-W05` | Cobertura de testes: ≥90% nas linhas da capability. |
