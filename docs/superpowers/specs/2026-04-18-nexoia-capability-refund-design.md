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
  → LLM identifica intenção e coleta motivo + email + CPF
    → LLM chama verificar_elegibilidade_reembolso(motivo, email, cpf)
      → Busca compra na Hubla → verifica prazo CDC (7 dias)
        → Dentro do prazo: LLM chama oferecer_retencao() (N1 → N2)
          → Recusa dupla ou compra duplicada: LLM chama processar_reembolso()
        → Fora do prazo: LLM informa data da compra
```

---

## 2. Escopo

### O que faz

- Capability reativa — LLM decide quando acionar as skills de reembolso com base na intenção do aluno
- LLM coleta motivo, email e CPF antes de chamar qualquer skill
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
src/nexoia/application/use_cases/refund/
    verificar_elegibilidade.py     # CDC 7 dias, Art.49, compra duplicada, is_recurring
    iniciar_retencao.py            # N1 → N2, nunca repetir oferta
    processar_reembolso.py         # mutex + HublaPort.process_refund() + invariantes
src/nexoia/domain/entities/refund_case.py
src/nexoia/domain/ports/hubla_port.py
src/nexoia/domain/ports/refund_mutex.py            # RefundMutexPort (interface)
src/nexoia/infrastructure/hubla/client.py          # stub HublaClient (Playwright)
src/nexoia/infrastructure/hubla/schemas.py         # HublaPurchase, RefundResult
src/nexoia/infrastructure/redis/refund_mutex.py    # RedisRefundMutex implementa RefundMutexPort
src/nexoia/infrastructure/skills/refund.py         # make_refund_skills() factory
src/nexoia/infrastructure/db/repositories/refund_case_repo.py
migrations/xxxx_add_refund_cases_table.py
tests/unit/use_cases/test_refund.py
tests/integration/test_refund_flow.py
```

### Modificados
```
src/nexoia/infrastructure/langgraph_runtime/graph_builder.py  # + make_refund_skills(...)
src/nexoia/config/settings.py                      # + REFUND_DEADLINE_DAYS=7
docs/superpowers/OPEN_QUESTIONS.md                 # + CQ-R01, CQ-R02, CQ-R03, CQ-R04
```

---

## 4. Use Cases e Skills

### 4.1 Use Cases (`application/use_cases/refund/`)

Regra de negócio pura — sem `@tool`, sem LangGraph. Cada use case recebe dependências via `__init__`.
Estado entre turnos é persistido em `RefundCase` no banco — sem `RefundState` no grafo.

**`VerificarElegibilidadeReembolso`**

Executado quando o LLM chama a skill com motivo + email + CPF do aluno.

1. Cria `RefundCase` com `status=COLLECTING`
2. **Crítico (PRD 7.3 Passo 2):** chama `HublaPort.get_purchase_by_email()` antes de qualquer menção a prazo
3. Calcula `days_since_purchase`:
   - Compra única: `today - purchase.created_at`
   - Compra recorrente (`is_recurring=True`): `today - purchase.first_charge_at` (PRD 7.3 Passo 2)
   - Compras separadas: cada `purchase_id` tem prazo independente
4. Verifica Art. 49 CDC: há registro de solicitação em canal anterior dentro do prazo (`LegalHistoryPort`)? → `within_deadline=True`
5. Detecta compra duplicada: mesmo contato com 2+ compras do mesmo produto → `is_duplicate_purchase=True`
6. Retorna resultado estruturado: elegível / inelegível (com data) / duplicada

**`IniciarRetencao`**

1. Valida que `within_deadline=True` e `is_duplicate_purchase=False`; retorna erro descritivo se não
2. Lê `RefundCase.offers_made` do banco — nunca repetir oferta já feita
3. Se N1 ainda não oferecido: retorna oferta N1 ao LLM (TODO CQ-R02)
4. Se N1 recusado e N2 não oferecido: retorna oferta N2
5. Se N2 recusado: retorna sinal `retention_exhausted=True` — LLM chama `processar_reembolso`
6. Atualiza `RefundCase.offers_made` e `status=IN_RETENTION`

**`ProcessarReembolso`**

Aplica invariantes de negócio antes de qualquer ação (Guards 1–4 da spec original — agora
aplicados como validação interna do use case, não como classes separadas):

- **Invariante 1 (ExplicitRequest):** pedido de reembolso explícito no turno atual? Detectado via LLM no contexto do `AgentState.messages[-1]`. Retorna erro descritivo se não.
- **Invariante 2 (ProductBlocked):** produto está em `refund_blocked_products` (persistido no `RefundCase`)? Retorna erro.
- **Invariante 3 (MandatoryRetention):** N2 foi oferecido após N1 recusado — exceto `is_duplicate_purchase=True`. Retorna erro.
- **Invariante 4 (SameTurn):** seta `refund_processed_this_turn=True` no `RefundCase`. O próximo turno limpa a flag — `pos_execucao` nunca encerra conversa se flag ativa.

Após validações:

1. Adquire mutex via `RefundMutexPort.acquire(account_id, contact_id, product_id)` — TTL 1h. Retorna erro se já adquirido (job duplicado).
2. Chama `HublaPort.process_refund(purchase_id, reason)` — stub TODO CQ-R01
3. Atualiza `RefundCase.status=REFUNDED`
4. Retorna **apenas** a mensagem padrão (PRD 7.3):
   > "Tô processando seu reembolso agora! O prazo de estorno de pix é até 72 horas e cartão de 1 a 2 faturas, ambos dependem da sua operadora. Você vai receber a confirmação assim que o processamento terminar, tá?"

### 4.2 Factory de Skills (`infrastructure/skills/refund.py`)

```python
def make_refund_skills(
    refund_repo: RefundCaseRepoPort,
    hubla: HublaPort,
    legal_history: LegalHistoryPort,
    refund_mutex: RefundMutexPort,
) -> list[BaseTool]:
    verificar_uc  = VerificarElegibilidadeReembolso(refund_repo, hubla, legal_history)
    reter_uc      = IniciarRetencao(refund_repo)
    processar_uc  = ProcessarReembolso(refund_repo, hubla, refund_mutex)

    @tool
    async def verificar_elegibilidade_reembolso(motivo: str, email: str, cpf: str) -> str:
        """
        Verifica elegibilidade do aluno para reembolso (CDC 7 dias).
        Use quando: aluno solicita reembolso e forneceu motivo + email + CPF.
        Não use quando: dados incompletos — colete-os conversacionalmente antes.
        Retorna: elegível / inelegível com data / compra duplicada.
        """
        cfg = get_config()["configurable"]
        return await verificar_uc.execute(cfg["account_id"], cfg["phone"], motivo, email, cpf)

    @tool
    async def oferecer_retencao() -> str:
        """
        Oferece retenção N1 ou N2 ao aluno elegível para reembolso.
        Use quando: aluno é elegível (dentro do prazo, não duplicada) e ainda não recusou N2.
        Não use quando: compra duplicada, N2 já recusado, ou aluno fora do prazo.
        Retorna: texto da oferta N1/N2 ou sinal de retenção esgotada.
        """
        cfg = get_config()["configurable"]
        return await reter_uc.execute(cfg["account_id"], cfg["phone"])

    @tool
    async def processar_reembolso() -> str:
        """
        Processa o reembolso após dupla recusa de retenção ou compra duplicada.
        Use quando: aluno recusou N1 e N2, OU compra duplicada confirmada.
        Não use quando: N2 ainda não foi oferecido — invariante bloqueará e retornará erro.
        Retorna: mensagem padrão de processamento (PRD 7.3).
        """
        cfg = get_config()["configurable"]
        return await processar_uc.execute(cfg["account_id"], cfg["phone"])

    return [verificar_elegibilidade_reembolso, oferecer_retencao, processar_reembolso]
```

### 4.3 `RefundMutexPort` (`domain/ports/refund_mutex.py`)

```python
class RefundMutexPort(Protocol):
    async def acquire(self, account_id: str, contact_id: str, product_id: str) -> bool: ...
    async def release(self, account_id: str, contact_id: str, product_id: str) -> None: ...
```

Implementação: `infrastructure/redis/refund_mutex.py`
`SETNX refund:mutex:{account_id}:{contact_id}:{product_id}` com TTL `REFUND_MUTEX_TTL_SECONDS` (3600s).

### 4.4 Fluxo LLM-orquestrado

```
Aluno pede reembolso
  → LegalMentionGuard (Core) — menção a Procon/advogado → handoff silencioso, zero mensagem
  → LLM coleta motivo + email + CPF conversacionalmente (sem skill)
    → LLM chama verificar_elegibilidade_reembolso(motivo, email, cpf)
      → Elegível + não duplicado → LLM chama oferecer_retencao()
          → N1 recusado → LLM chama oferecer_retencao() novamente (retorna N2)
            → N2 recusado → LLM chama processar_reembolso()
          → N1 ou N2 aceito → LLM entrega oferta conversacionalmente
      → Compra duplicada → LLM chama processar_reembolso() diretamente
      → Inelegível (fora do prazo) → LLM informa data da compra ao aluno
          → 3ª insistência → LLM chama escalar_para_humano (Core skill)
```

**Nota aluno CMP:** argumentação especial antes de N1/N2 — TODO CQ-R03. Stub por ora.

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
    is_recurring: bool                 # assinatura
    first_charge_at: datetime | None   # preenchido se is_recurring=True — prazo CDC conta daqui

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

### Guards e Invariantes

**Guard de conversa (Core — `domain/policies/guards/`):**
- `LegalMentionGuard` — menção a Procon/advogado/ação judicial → handoff silencioso pré-LLM

**Invariantes de negócio (aplicados dentro dos use cases — não são classes guard separadas):**

| Invariante | Onde é aplicado | Comportamento se violado |
|-----------|-----------------|--------------------------|
| ExplicitRefundRequest | `ProcessarReembolso.execute()` | Retorna erro descritivo ao LLM |
| ProductBlocked | `ProcessarReembolso.execute()` | Retorna erro descritivo ao LLM |
| MandatoryRetention | `ProcessarReembolso.execute()` | Retorna erro descritivo ao LLM |
| SameTurnBlock | `ProcessarReembolso.execute()` seta flag; `pos_execucao` verifica | Encerramento bloqueado no turno atual |

**Mutex Redis (port de infraestrutura):**
- `RefundMutexPort` — adquirido em `ProcessarReembolso.execute()` via DI
- Implementação: `infrastructure/redis/refund_mutex.py` — TTL 3600s

---

## 7. Configuração

```python
REFUND_DEADLINE_DAYS: int = 7       # prazo CDC Art. 49
REFUND_MUTEX_TTL_SECONDS: int = 3600 # TTL do mutex de reembolso (PRD 7.3 Guard 5: TTL 1h)
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

### Unitários (`tests/unit/use_cases/test_refund.py`)

| Teste | Cenário |
|-------|---------|
| `test_happy_path_refund` | Dentro do prazo, recusa N1+N2 → reembolso processado |
| `test_retention_n1_accepted` | Dentro do prazo, aceita N1 → oferta entregue, sem reembolso |
| `test_retention_n2_accepted` | Recusa N1, aceita N2 → oferta entregue |
| `test_deny_outside_deadline` | Compra > 7 dias → retorna inelegível com data |
| `test_duplicate_purchase_skips_retention` | Compra duplicada → `processar_reembolso` direto |
| `test_art49_forces_within_deadline` | Solicitação anterior no prazo → `within_deadline=True` |
| `test_mutex_blocks_duplicate_job` | `RefundMutexPort.acquire()` retorna False → erro descritivo |
| `test_mandatory_retention_invariant` | `processar_reembolso` sem N2 oferecido → erro descritivo |
| `test_same_turn_block_flag` | `refund_processed_this_turn=True` sinaliza bloqueio de encerramento |
| `test_recurring_purchase_uses_first_charge_date` | `is_recurring=True` → prazo CDC a partir de `first_charge_at` |

### Integração (`tests/integration/test_refund_flow.py`)

- `FakeHublaClient` e `FakeLegalHistoryPort` e `FakeRefundMutexPort` como adapters
- Valida `RefundCase` persistido corretamente (testcontainers)
- Valida mutex Redis real funcionando entre dois workers simultâneos
- Valida fluxo completo via skills: verificar → oferecer → processar

---

## 10. Requisitos Funcionais

| ID | Requisito |
|----|-----------|
| `RF-R01` | LLM coleta motivo + email + CPF conversacionalmente antes de invocar qualquer skill. |
| `RF-R02` | `HublaPort.get_purchase_by_email()` verifica prazo CDC: ≤ 7 dias = dentro, > 7 = fora. |
| `RF-R03` | Art. 49 CDC: se houver registro de solicitação em canal anterior dentro do prazo, `within_deadline = True`. |
| `RF-R04` | Compra duplicada: processa reembolso sem tentativa de retenção. |
| `RF-R05` | Retenção: máx 2 ofertas (N1 → N2). Nunca repetir a mesma oferta. |
| `RF-R06` | Ofertas N1/N2 por produto: **TODO** — ver CQ-R02. Stub por ora. |
| `RF-R07` | Aluno CMP: argumentação especial antes de N1/N2. **TODO** — ver CQ-R03. |
| `RF-R08` | Após recusa dupla: `HublaPort.process_refund()` + mensagem padrão. **Nunca dizer "fizemos" ou "processado"**. |
| `RF-R09` | Deny fora do prazo: informa data da compra. Na 3ª insistência: handoff silencioso. |
| `RF-R10` | Menção a Procon/advogado/ação judicial: handoff silencioso imediato, zero mensagem (Guard 0). |
| `RF-R11` | `process_refund`: stub via Playwright — ver CQ-R01. |
| `RF-R12` | Mutex Redis Guard 5 por `(account_id, contact_id, product_id)` evita job duplicado (TTL 1h). |
| `RF-R13` | Compra recorrente (`is_recurring=True`): prazo conta da primeira parcela (PRD 7.3 Passo 2). |
| `RF-R14` | Compras separadas: cada `purchase_id` tem prazo independente. |
| `RF-R15` | **Guard 1 (ExplicitRefundRequest):** bloqueia `process_refund` se aluno não pediu explicitamente neste turno. |
| `RF-R16` | **Guard 2 (ProductBlocked):** se aluno disse "não quero cancelar X", bloqueia `process_refund` para X. |
| `RF-R17` | **Guard 3 (MandatoryRetention):** bloqueia `process_refund` se N2 não oferecido após N1 recusado (exceto duplicate/CMP). |
| `RF-R18` | **Guard 4 (SameTurnBlock):** nunca chamar `finish_attendance` no mesmo turno que `process_refund`. |
| `RF-R19` | **Crítico:** nunca falar sobre prazo sem ter buscado a compra na Hubla antes (PRD 7.3 Passo 2). |

## 11. Requisitos Não-Funcionais

| ID | Requisito |
|----|-----------|
| `RNF-R01` | Tenant isolation: toda query filtra por `account_id`. |
| `RNF-R02` | Estado entre turnos persistido via checkpoint LangGraph. |
| `RNF-R03` | Circuit breaker herdado do Core aplicado ao `HublaClient`. |
| `RNF-R04` | Cobertura de testes: ≥90% nas linhas da capability. |
| `RNF-R05` | Idle/timeout gerenciado pelo Core — sem lógica própria. |
