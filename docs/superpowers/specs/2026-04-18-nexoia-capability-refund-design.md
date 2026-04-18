# Spec ④ — Capability Refund & Retention

**Data:** 2026-04-18
**Fase:** 1
**Repositório alvo:** `nexoia-agent`
**Depende de:** Spec ① (Core — mutex Redis, LegalMentionGuard, handoff), Spec ② (AccessCase)
**Status:** Design aprovado — aguardando plano de implementação

---

## 1. Contexto e Objetivo

A Capability Refund & Retention é o fluxo reativo acionado quando o aluno pede reembolso. É o fluxo mais crítico do sistema — envolve decisões com impacto financeiro direto, compliance com o Art. 49 do CDC, e tentativas de retenção antes de processar o estorno.

**Resumo do fluxo:**
```
Aluno pede reembolso
  → Intent Router classifica intent = "refund"
    → Worker invoca subgraph Refund
      → Coleta motivo + email + CPF
        → Busca compra na Hubla → verifica prazo CDC (7 dias)
          → Dentro do prazo: tenta retenção (N1 → N2)
            → Recusa dupla ou compra duplicada: processa reembolso
          → Fora do prazo: nega com informação da data
```

---

## 2. Escopo

### O que faz

- Subgraph LangGraph acionado quando `intent = "refund"`
- Coleta motivo, email e CPF do aluno (juntos, na mesma mensagem)
- Busca compra na Hubla via `HublaPort.get_purchase_by_email()` (stub — ver CQ-R04)
- Verifica prazo CDC: `dias_desde_compra <= REFUND_DEADLINE_DAYS (7)`
- Aplica exceção Art. 49 CDC: solicitação em canal anterior dentro do prazo → processa sem retenção
- Tenta retenção: N1 → N2 (máx 2 ofertas, nunca repetir a mesma)
- Exceção compra duplicada: processa reembolso sem retenção
- Exceção aluno CMP: argumentação especial (TODO — ver CQ-R03)
- Processa reembolso via `HublaPort.process_refund()` (stub — ver CQ-R01)
- Nega reembolso fora do prazo com mensagem informativa
- Guards: `LegalMentionGuard` (Core) + `RefundMutexGuard` (novo)

### O que NÃO faz

- Não implementa `HublaPort.process_refund()` real — stub com TODO (CQ-R01)
- Não implementa `HublaPort.get_purchase_by_email()` real — stub com TODO (CQ-R04)
- Não define ofertas N1/N2 por produto — TODO (CQ-R02)
- Não define comportamento de aluno CMP — TODO (CQ-R03)
- Não gerencia idle/timeout — Core cuida (30min ping + 20min close)

---

## 3. Arquivos

### Novos
```
src/nexoia/application/capabilities/refund.py
src/nexoia/domain/entities/refund_case.py
src/nexoia/domain/ports/hubla_port.py
src/nexoia/infrastructure/hubla/client.py          # stub HublaClient
src/nexoia/infrastructure/hubla/schemas.py         # HublaPurchase, RefundResult
src/nexoia/application/guards/refund_mutex.py      # RefundMutexGuard
src/nexoia/infrastructure/db/repositories/refund_case_repo.py
migrations/xxxx_add_refund_cases_table.py
tests/unit/capabilities/test_refund.py
tests/integration/test_refund_flow.py
```

### Modificados
```
src/nexoia/application/intent_router.py            # + intent "refund"
src/nexoia/config/settings.py                      # + REFUND_DEADLINE_DAYS=7
docs/superpowers/OPEN_QUESTIONS.md                 # + CQ-R01, CQ-R02, CQ-R03, CQ-R04
```

---

## 4. Subgraph LangGraph

### Grafo de nós

```
START
  │
  ▼
collect             ← coleta motivo + email + CPF (se não vieram na 1ª mensagem)
  │
  ▼
check_deadline      ← busca compra na Hubla → calcula dias → dentro/fora do prazo
  │                   Art. 49 CDC: canal anterior dentro do prazo → força within_deadline=True
  ├─ fora do prazo ──────────────────────────────────► deny → END
  ├─ compra duplicada ───────────────────────────────► process_refund → END
  │
  ▼
retention_loop      ← oferece N1 → aguarda resposta → se recusa, oferece N2
  │                   máx 2 ofertas; nunca repetir; aluno CMP → argumentação especial (TODO CQ-R03)
  ├─ aceite ────────────────────────────────────────► deliver_offer → END
  ├─ recusa dupla ──────────────────────────────────► process_refund → END
  │
  ▼
process_refund      ← HublaPort.process_refund() stub → mensagem padrão
  │
  ▼
END
```

**Guards aplicados em todo nó:**
- `LegalMentionGuard` (Core) — menção a Procon/advogado/ação judicial → **handoff silencioso imediato, zero mensagem ao aluno**
- `RefundMutexGuard` (novo) — Redis mutex por `(account_id, contact_id, product_id)` → evita job duplicado de reembolso

### Estado do subgraph

```python
class RefundState(ConversationState):
    refund_case_id: str | None
    student_email: str | None
    student_cpf: str | None
    refund_reason: str | None
    purchase: HublaPurchase | None       # resultado de get_purchase_by_email
    days_since_purchase: int | None
    within_deadline: bool | None         # True = dentro dos 7 dias CDC
    is_duplicate_purchase: bool          # True = pula retenção
    is_cmp_student: bool                 # TODO CQ-R03
    offers_made: list[str]               # ["N1"] ou ["N1","N2"] — nunca repetir
    offer_accepted: bool
    refund_processed: bool
    refund_step: RefundStep              # enum: COLLECT/DEADLINE/RETENTION/PROCESS/DENY/DONE
```

### Nó `collect`

1. Se motivo já veio na 1ª mensagem: extrai via LLM e salva em `refund_reason`
2. Se motivo ausente: envia 1 frase de empatia + pede motivo
3. Pede email + CPF **juntos** na mesma mensagem
4. Quando dados chegam: cria `RefundCase` com `status = COLLECTING`, avança para `check_deadline`

### Nó `check_deadline`

1. Chama `HublaPort.get_purchase_by_email(email, account_id)` — stub (TODO CQ-R04)
2. Calcula `days_since_purchase = today - purchase.created_at`
3. Se `days_since_purchase > REFUND_DEADLINE_DAYS`: `within_deadline = False` → `deny`
4. Verifica Art. 49 CDC: há registro de solicitação em canal anterior dentro do prazo? → `within_deadline = True` (força processamento)
5. Verifica compra duplicada: mesmo `contact_id` com 2+ purchases do mesmo produto → `is_duplicate_purchase = True`
6. Atualiza `RefundCase.status = CHECKING_DEADLINE`

### Nó `retention_loop`

1. Se `is_duplicate_purchase = True`: pula direto para `process_refund`
2. Se `is_cmp_student = True`: aplica argumentação especial (TODO CQ-R03) — stub por ora
3. Se N1 não ofertado: envia oferta N1, aguarda resposta, seta `offers_made = ["N1"]`
4. Se N1 recusado e N2 não ofertado: envia oferta N2, aguarda resposta, seta `offers_made = ["N1","N2"]`
5. Se aceite: `offer_accepted = True` → `deliver_offer`
6. Se N2 recusado: vai para `process_refund`

> **TODO — CQ-R02:** Confirmar se ofertas N1/N2 variam por produto ou são fixas para todos.

### Nó `deliver_offer`

- Entrega o benefício aceito (Acesso Vitalício ou Mentoria de Tráfego)
- Atualiza `RefundCase.status = OFFER_ACCEPTED`
- Cancela qualquer job de idle pendente (Core cuida)

### Nó `process_refund`

1. Chama `HublaPort.process_refund(purchase_id, reason)` — stub (TODO CQ-R01)
2. Envia mensagem padrão:
   > "Tô processando seu reembolso agora! O prazo de estorno de pix é até 72 horas e cartão de 1 a 2 faturas, ambos dependem da sua operadora. Você vai receber a confirmação assim que o processamento terminar, tá?"
3. Atualiza `RefundCase.status = REFUNDED`

### Nó `deny`

1. Informa data da compra e que o prazo de 7 dias passou
2. Na 3ª insistência após o deny: escala silenciosamente para humano
3. Atualiza `RefundCase.status = DENIED`

---

## 5. Entidade e Modelo de Dados

### `RefundCase` (`domain/entities/refund_case.py`)

```python
@dataclass
class RefundCase:
    id: str                          # UUID
    account_id: int                  # multi-tenancy
    contact_id: str
    conversation_id: str
    purchase_id: str | None          # vem da Hubla se encontrado
    product_name: str | None
    student_email: str
    student_cpf: str | None
    refund_reason: str | None
    days_since_purchase: int | None
    within_deadline: bool | None
    offers_made: list[str]           # JSONB — ["N1", "N2"]
    offer_accepted: bool
    status: RefundCaseStatus
    created_at: datetime
    updated_at: datetime
```

### `RefundCaseStatus`

```python
class RefundCaseStatus(str, Enum):
    COLLECTING        = "collecting"
    CHECKING_DEADLINE = "checking_deadline"
    IN_RETENTION      = "in_retention"
    OFFER_ACCEPTED    = "offer_accepted"
    REFUNDED          = "refunded"
    DENIED            = "denied"
    ESCALATED         = "escalated"
```

### Tabela `refund_cases`

```sql
CREATE TABLE refund_cases (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id          INTEGER NOT NULL,
    contact_id          TEXT NOT NULL,
    conversation_id     TEXT NOT NULL,
    purchase_id         TEXT,
    product_name        TEXT,
    student_email       TEXT NOT NULL,
    student_cpf         TEXT,
    refund_reason       TEXT,
    days_since_purchase INTEGER,
    within_deadline     BOOLEAN,
    offers_made         JSONB NOT NULL DEFAULT '[]',
    offer_accepted      BOOLEAN NOT NULL DEFAULT FALSE,
    status              TEXT NOT NULL DEFAULT 'collecting',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_refund_cases_account_contact ON refund_cases(account_id, contact_id);
```

---

## 6. Ports e Adapters

### `HublaPort` (`domain/ports/hubla_port.py`)

```python
class HublaPort(Protocol):
    async def get_purchase_by_email(self, email: str, account_id: int) -> HublaPurchase | None: ...
    async def process_refund(self, purchase_id: str, reason: str) -> RefundResult: ...
```

### `HublaPurchase` e `RefundResult` (value objects)

```python
@dataclass(frozen=True)
class HublaPurchase:
    id: str
    product_name: str
    created_at: datetime
    amount: float
    is_duplicate: bool

@dataclass(frozen=True)
class RefundResult:
    success: bool
    refund_id: str | None
    error: str | None
```

### `HublaClient` (stub)

```python
# ⚠️  TODO CQ-R01: implementar process_refund com mecanismo real (API Hubla ou Playwright)
# ⚠️  TODO CQ-R04: verificar se Hubla tem endpoint get_purchase_by_email
# ANTES DE IMPLEMENTAR: consultar OPEN_QUESTIONS.md
class HublaClient:
    async def get_purchase_by_email(self, email: str, account_id: int) -> HublaPurchase | None:
        raise NotImplementedError("HublaClient não implementado — ver OPEN_QUESTIONS.md CQ-R04")

    async def process_refund(self, purchase_id: str, reason: str) -> RefundResult:
        raise NotImplementedError("HublaClient não implementado — ver OPEN_QUESTIONS.md CQ-R01")
```

### `RefundMutexGuard` (`application/guards/refund_mutex.py`)

```python
# Redis mutex por (account_id, contact_id, product_id)
# Evita dois jobs de reembolso simultâneos para o mesmo aluno+produto
# TTL: 10 minutos (tempo suficiente para o fluxo completar)
```

---

## 7. Configuração

```python
REFUND_DEADLINE_DAYS: int = 7       # prazo CDC Art. 49
REFUND_MUTEX_TTL_SECONDS: int = 600 # TTL do mutex de reembolso
```

---

## 8. Observabilidade

### Logs estruturados

Cada nó loga: `capability=refund`, `node`, `account_id`, `refund_case_id`, `refund_step`

- Prazo excedido → `level=INFO`, `days_since_purchase`, `status=denied`
- Oferta feita → `level=INFO`, `offer=N1|N2`
- Oferta aceita → `level=INFO`, `offer`, `status=offer_accepted`
- Reembolso processado → `level=INFO`, `purchase_id`, `status=refunded`
- Guard jurídico disparado → `level=WARNING`, `reason=legal_mention`, handoff imediato
- Mutex bloqueou → `level=WARNING`, `reason=duplicate_refund_job`

### Métricas Prometheus

```
refund_capability_total{status="refunded"|"denied"|"offer_accepted"|"escalated"|"error"}
refund_retention_offer_total{offer="N1"|"N2"}
refund_retention_acceptance_rate (gauge)
refund_deadline_check_total{result="within"|"exceeded"}
```

---

## 9. Testes

### Unitários (`tests/unit/capabilities/test_refund.py`)

| Teste | Cenário |
|-------|---------|
| `test_happy_path_refund` | Dentro do prazo, recusa N1+N2 → reembolso processado |
| `test_retention_n1_accepted` | Dentro do prazo, aceita N1 → deliver_offer, sem reembolso |
| `test_retention_n2_accepted` | Recusa N1, aceita N2 → deliver_offer |
| `test_deny_outside_deadline` | Compra > 7 dias → deny com data informada |
| `test_duplicate_purchase_skips_retention` | Compra duplicada → reembolso sem ofertas |
| `test_legal_mention_immediate_handoff` | "vou acionar o Procon" → handoff silencioso imediato |
| `test_art49_forces_within_deadline` | Solicitação anterior no prazo → processa mesmo com data expirada |
| `test_mutex_blocks_duplicate_job` | 2 jobs simultâneos → segundo bloqueado pelo mutex |
| `test_deny_escalate_on_third_insistence` | 3 insistências após deny → handoff |

### Integração (`tests/integration/test_refund_flow.py`)

- `FakeHublaClient` e `FakeChatNexoClient` como adapters
- Valida `RefundCase` persistido corretamente (testcontainers)
- Valida mutex Redis funcionando entre dois workers simultâneos
- Valida estado entre turnos via checkpoint LangGraph (collect → deadline → retention → process)

---

## 10. Requisitos Funcionais

| ID | Requisito |
|----|-----------|
| `RF-R01` | Coleta motivo + email + CPF juntos na mesma mensagem. Se motivo vier na 1ª mensagem, extrai via LLM. |
| `RF-R02` | `HublaPort.get_purchase_by_email()` verifica prazo CDC: ≤ 7 dias = dentro, > 7 = fora. |
| `RF-R03` | Art. 49 CDC: se houver registro de solicitação em canal anterior dentro do prazo, `within_deadline = True`. |
| `RF-R04` | Compra duplicada: processa reembolso sem tentativa de retenção. |
| `RF-R05` | Retenção: máx 2 ofertas (N1 → N2). Nunca repetir a mesma oferta. |
| `RF-R06` | Ofertas N1/N2 por produto: **TODO** — ver CQ-R02. Stub por ora. |
| `RF-R07` | Aluno CMP: argumentação especial antes de N1/N2. **TODO** — ver CQ-R03. |
| `RF-R08` | Após recusa dupla: `HublaPort.process_refund()` + mensagem padrão. |
| `RF-R09` | Deny fora do prazo: informa data da compra. Na 3ª insistência: handoff silencioso. |
| `RF-R10` | Menção a Procon/advogado/ação judicial: handoff silencioso imediato, zero mensagem. |
| `RF-R11` | `process_refund`: **TODO** — ver CQ-R01. Stub com `NotImplementedError`. |
| `RF-R12` | Mutex Redis por `(account_id, contact_id, product_id)` evita job duplicado (TTL 10min). |

## 11. Requisitos Não-Funcionais

| ID | Requisito |
|----|-----------|
| `RNF-R01` | Tenant isolation: toda query filtra por `account_id`. |
| `RNF-R02` | Estado entre turnos persistido via checkpoint LangGraph. |
| `RNF-R03` | Circuit breaker herdado do Core aplicado ao `HublaClient`. |
| `RNF-R04` | Cobertura de testes: ≥90% nas linhas da capability. |
| `RNF-R05` | Idle/timeout gerenciado pelo Core — sem lógica própria. |
