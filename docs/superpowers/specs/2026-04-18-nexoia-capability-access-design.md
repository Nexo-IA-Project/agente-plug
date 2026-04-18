# Spec ③ — Capability Access

**Data:** 2026-04-18
**Fase:** 1
**Repositório alvo:** `nexoia-agent`
**Depende de:** Spec ① (Core), Spec ② (AccessCase, CademiPort, AccessCaseStatus)
**Status:** Design aprovado — aguardando plano de implementação

---

## 1. Contexto e Objetivo

A Capability Access é o fluxo **reativo** acionado quando o aluno manda mensagem reclamando de problema de acesso à plataforma. Diferente da Welcome (spec ②), que age de forma proativa logo após a compra, a Access entra em ação quando o aluno já está frustrado e precisando de ajuda.

Como a NexoIA sempre envia a boas-vindas assim que a compra é confirmada, o `AccessCase` do aluno já existe antes de qualquer mensagem chegar. Isso significa que sempre temos email, CPF (quando enviado pela Hubla) e nome disponíveis — sem precisar perguntar ao aluno na maioria dos casos.

**Resumo do fluxo:**
```
Aluno manda mensagem sobre acesso
  → Intent Router classifica intent = "access"
    → Worker invoca subgraph Access
      → Busca AccessCase pelo telefone do aluno
        → Busca em cascata na Cademi (email → CPF → nome+telefone)
          → Envia link/dados de acesso
            → Atualiza AccessCase (status = REACTIVE_LINK_SENT)
```

---

## 2. Escopo

### O que a Capability Access FAZ

- Subgraph LangGraph plugado no main graph do Core, acionado quando `intent = "access"`
- Busca `AccessCase` ativo pelo `contact_phone` (dados de compra já persistidos)
- Busca aluno na Cademi em cascata: email → CPF → nome+telefone (máx 3 tentativas)
- Se CPF não disponível no AccessCase: pede CPF ao aluno como fallback
- Envia link/dados de acesso via ChatNexo
- Atualiza `AccessCase` com novo status e contador de tentativas
- Escala silenciosamente para humano após 3 tentativas sem resultado

### O que NÃO FAZ

- Não processa compras novas (spec ②)
- Não trata reembolso (spec ④)
- Não implementa o `CademiClient` real — stub com TODO explícito (herdado do spec ②)
- Não gerencia idle/timeout — responsabilidade do Core (30min ping + 20min close)
- Não trata problemas de cadastro Shopee ou KYC — plataformas distintas (PRD 7.2)

---

## 3. Arquivos

### Novos
```
src/nexoia/application/capabilities/access.py          # subgraph + lógica
tests/unit/capabilities/test_access.py
tests/integration/test_access_flow.py
migrations/xxxx_add_access_case_reactive_fields.py     # student_cpf, search_attempts
```

### Modificados
```
src/nexoia/domain/entities/access_case.py              # + student_cpf, search_attempts, novos status
src/nexoia/interface/http/routers/webhook_purchase.py  # + document no schema Pydantic (Hubla)
src/nexoia/infrastructure/db/repositories/access_case_repo.py  # + find_by_phone, update_status
docs/superpowers/OPEN_QUESTIONS.md                     # + CQ-A01, CQ-A02
```

---

## 4. Subgraph LangGraph

### Grafo de nós

```
START
  │
  ▼
lookup_access_case      ← busca AccessCase ativo pelo contact_phone
  │ se não encontrado → handoff silencioso
  ▼
check_platform_scope    ← se aluno menciona Shopee/KYC → handoff silencioso (plataformas distintas)
  │
  ▼
search_cademi_cascade   ← email → CPF → nome+telefone; máx 3 tentativas
  │ se email da mensagem difere do AccessCase → oferece atualizar cadastro antes de reenviar
  │ se esgotado → handoff silencioso + status = REACTIVE_ESCALATED
  ▼
send_access             ← envia link nominal de auto-login via ChatNexo (PRD 7.2)
  │
  ▼
update_access_case      ← status = REACTIVE_LINK_SENT, search_attempts, updated_at
  │
  ▼
END
```

### Estado do subgraph

```python
class AccessState(ConversationState):
    access_case_id: str | None
    student_email: str | None
    student_cpf: str | None        # do AccessCase; None se Hubla não enviou
    student_name: str | None
    student_phone: str | None
    cademi_student: CademiStudent | None
    search_attempts: int           # contador de tentativas (máx 3)
    cpf_asked: bool                # True se pedimos CPF ao aluno (fallback)
    access_link: str | None        # TODO: confirmar com cliente — ver CQ-A01
```

### Nó `lookup_access_case`

1. Busca `AccessCase` com `contact_phone = state.student_phone AND account_id = state.account_id`
2. Ordena por `created_at DESC` — pega o mais recente
3. Se não encontrado: dispara handoff silencioso (caso raro — aluno sem compra registrada)
4. Popula `student_email`, `student_cpf`, `student_name` a partir do `AccessCase`

### Nó `check_platform_scope`

**Crítico (PRD 7.2):** *"Nunca usar `resend_access` para problemas de cadastro Shopee ou KYC — são plataformas distintas."*

1. Analisa a mensagem do aluno via LLM para detectar menções a Shopee ou KYC
2. Se detectar: dispara `ChatNexoClient.transfer_to_human(reason="shopee_or_kyc_out_of_scope")` — handoff silencioso
3. Caso contrário: prossegue para `search_cademi_cascade`

### Nó `search_cademi_cascade`

**Regra PRD 7.2 — email mismatch:** se o aluno fornecer um email na mensagem (ex: "tentei com joao@gmail.com") e for **diferente** do email no `AccessCase`:
1. A IA responde oferecendo atualizar o cadastro: *"Percebi que o email que você passou é diferente do cadastro. Quer que eu atualize pra esse novo email antes de reenviar o acesso?"*
2. Se aluno confirmar: atualiza `long_term_facts.email` do contato + tenta busca Cademi com o email novo
3. Se aluno negar: prossegue com o email do AccessCase

Tentativa 1 — email:
1. Chama `CademiPort.get_student_by_email(student_email)`
2. Se encontrado: `cademi_student = resultado`, prossegue para `send_access`

Tentativa 2 — CPF:
1. Se `student_cpf` disponível: chama `CademiPort.get_student_by_cpf(student_cpf)`
2. Se `student_cpf` é `None`: envia mensagem ao aluno pedindo CPF, seta `cpf_asked=True`, aguarda próxima mensagem
3. Quando CPF chega (próximo turno): chama `get_student_by_cpf(cpf_recebido)`
4. Se encontrado: prossegue para `send_access`

Tentativa 3 — nome + telefone:
1. Chama busca por nome+telefone na Cademi

> **TODO — ver CQ-A02:** Verificar se a Cademi API suporta busca por nome+telefone antes de implementar. Stub com `NotImplementedError` enquanto não confirmado.

Esgotado (3 tentativas sem resultado):
- `search_attempts = 3`
- Dispara `ChatNexoClient.transfer_to_human(reason="cademi_not_found_after_3_attempts")`
- Atualiza `AccessCase.status = REACTIVE_ESCALATED`

### Nó `send_access`

**Regra PRD 7.2:** *"Link de acesso deve ser nominal (auto-login) — aluno não cria senha."*

1. Chama `CademiPort.get_access_link(cademi_student.id, product_id)`
2. Envia via `ChatNexoClient.send_message(...)` com link nominal de auto-login (dentro da janela 24h = texto livre; fora = template Meta)

### Nó `update_access_case`

- `access_case.status = REACTIVE_LINK_SENT`
- `access_case.search_attempts = state.search_attempts`
- `access_case.updated_at = now()`

---

## 5. Entidade e Modelo de Dados

### Atualizações no `AccessCase` (spec ②)

```python
@dataclass
class AccessCase:
    # campos existentes (spec ②) ...
    id: str
    account_id: int
    contact_id: str
    conversation_id: str
    purchase_id: str
    product_name: str
    access_link: str | None
    status: AccessCaseStatus
    access_confirmed: bool
    scheduled_d1_job_id: str | None
    created_at: datetime
    updated_at: datetime
    # novos (spec ③)
    student_cpf: str | None        # campo `document` do webhook Hubla (CPF, CNPJ ou None)
    search_attempts: int           # contador de tentativas na Cademi (padrão 0)
```

### Novos status no `AccessCaseStatus`

```python
class AccessCaseStatus(str, Enum):
    # existentes (spec ②)
    PENDING            = "pending"
    LINK_SENT          = "link_sent_proativo"
    ACCESSED           = "accessed"
    REMINDED_D1        = "reminded_d1"
    ESCALATED          = "escalated"
    # novos (spec ③)
    REACTIVE_LINK_SENT = "reactive_link_sent"   # aluno pediu ajuda → enviamos acesso
    REACTIVE_ESCALATED = "reactive_escalated"    # 3 tentativas falharam → handoff
```

### Migration Alembic

```sql
ALTER TABLE access_cases
    ADD COLUMN student_cpf     TEXT,
    ADD COLUMN search_attempts INTEGER NOT NULL DEFAULT 0;
```

### Atualização no payload Hubla (spec ①)

Schema Pydantic do `POST /webhook/purchase` recebe campo novo:

```python
class PurchaseWebhookPayload(BaseModel):
    purchase_id: str
    nome: str
    email: str
    telefone: str
    produto: str
    valor: float
    timestamp: datetime
    document: str | None = None    # CPF ou CNPJ do comprador; None se não enviado
```

O valor é persistido em `access_cases.student_cpf` ao criar o `AccessCase`.

---

## 6. Ports (sem mudanças)

`CademiPort` herdado do spec ② já tem os métodos necessários:

```python
class CademiPort(Protocol):
    async def get_student_by_email(self, email: str) -> CademiStudent | None: ...
    async def get_student_by_cpf(self, cpf: str) -> CademiStudent | None: ...
    async def get_access_link(self, student_id: str, product_id: str) -> str: ...
```

> **TODO — CQ-A02:** Se a Cademi suportar busca por nome+telefone, adicionar método `get_student_by_name_phone` ao Port e ao stub.

---

## 7. Configuração

Nenhuma variável nova de ambiente. A capability herda as configs do Core e do spec ②:
- `CADEMI_API_URL`, `CADEMI_API_KEY`, `CADEMI_MAX_RETRIES` (spec ②)
- `IDLE_PING_MINUTES`, `IDLE_CLOSE_MINUTES` (Core)

---

## 8. Observabilidade

### Logs estruturados (structlog)

Cada nó loga: `capability=access`, `node`, `account_id`, `access_case_id`, `search_attempts`

- AccessCase não encontrado → `level=WARNING`, `reason=no_access_case`, handoff disparado
- Cada tentativa Cademi → `level=INFO`, `attempt`, `method` (email/cpf/name_phone)
- CPF pedido ao aluno → `level=INFO`, `reason=cpf_not_in_hubla_payload`
- 3 tentativas esgotadas → `level=WARNING`, `reason=cademi_not_found`, handoff disparado
- Acesso enviado → `level=INFO`, `conversation_id`

### Métricas Prometheus

```
access_capability_total{status="success"|"escalated"|"no_access_case"|"error"}
access_cademi_cascade_attempts (histogram — distribuição de tentativas até encontrar)
access_cpf_fallback_total        # vezes que pedimos CPF ao aluno
```

---

## 9. Testes

### Unitários (`tests/unit/capabilities/test_access.py`)

| Teste | Cenário |
|-------|---------|
| `test_happy_path_by_email` | Cademi encontra na 1ª tentativa (email) → acesso enviado |
| `test_found_by_cpf_stored` | Email falha, CPF disponível no AccessCase → acesso enviado |
| `test_cpf_not_in_case_asks_student` | CPF = None → IA pede CPF ao aluno → recebe → encontra → envia |
| `test_escalation_after_3_attempts` | 3 tentativas falham → handoff silencioso + REACTIVE_ESCALATED |
| `test_no_access_case_handoff` | Sem AccessCase para o telefone → handoff silencioso |
| `test_access_case_status_updated` | Happy path → AccessCase.status = REACTIVE_LINK_SENT |

### Integração (`tests/integration/test_access_flow.py`)

- `FakeCademiClient` e `FakeChatNexoClient` como adapters de teste
- Valida `AccessCase` atualizado corretamente no PostgreSQL (testcontainers)
- Valida handoff chamado quando 3 tentativas falham
- Valida fluxo de CPF: estado salvo entre turnos via checkpoint LangGraph

---

## 10. Requisitos Funcionais

| ID | Requisito |
|----|-----------|
| `RF-A01` | Busca `AccessCase` pelo `contact_phone` + `account_id`. Se não encontrado: handoff silencioso. |
| `RF-A02` | Cascade de busca Cademi: email (1ª) → CPF stored (2ª) → nome+telefone (3ª). Máx 3 tentativas. |
| `RF-A03` | Se `student_cpf = None`: envia mensagem pedindo CPF ao aluno. Retoma busca na próxima mensagem. |
| `RF-A04` | Após 3 tentativas sem resultado: `transfer_to_human`, `status = REACTIVE_ESCALATED`. |
| `RF-A05` | Envia link nominal de auto-login (PRD 7.2). Dentro de janela 24h: texto livre. Fora: template Meta. |
| `RF-A05a` | Se aluno mencionar Shopee ou KYC: handoff silencioso (plataformas distintas — PRD 7.2). |
| `RF-A05b` | Se aluno fornecer email ≠ email no AccessCase: oferecer atualizar cadastro antes de reenviar (PRD 7.2). |
| `RF-A06` | Busca Cademi por nome+telefone (3ª tentativa): **TODO** — ver CQ-A02. Stub com `NotImplementedError`. |
| `RF-A07` | Payload Hubla inclui campo `document` (CPF/CNPJ/None). Persistido em `student_cpf` no AccessCase. |
| `RF-A08` | `AccessCase` atualizado com `REACTIVE_LINK_SENT` e `search_attempts` após envio bem-sucedido. |

## 11. Requisitos Não-Funcionais

| ID | Requisito |
|----|-----------|
| `RNF-A01` | Tenant isolation: toda query filtra por `account_id`. |
| `RNF-A02` | Estado entre turnos (ex: aguardando CPF do aluno) persistido via checkpoint LangGraph. |
| `RNF-A03` | Circuit breaker herdado do Core aplicado ao `CademiClient`. |
| `RNF-A04` | Cobertura de testes: ≥90% nas linhas da capability. |
| `RNF-A05` | Idle/timeout gerenciado pelo Core (30min ping + 20min close) — sem lógica própria. |
