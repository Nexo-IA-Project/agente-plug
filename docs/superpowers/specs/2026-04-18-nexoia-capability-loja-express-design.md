# Spec ⑤ — Capability Loja Express

**Data:** 2026-04-18
**Fase:** 1
**Repositório alvo:** `nexoia-agent`
**Depende de:** Spec ① (Core — Scheduler, Lifecycle Manager), Spec ② (padrão de subgraph proativo)
**Status:** Design aprovado — aguardando plano de implementação

---

## 1. Contexto e Objetivo

A Capability Loja Express acompanha o aluno durante os 7 dias após a compra de um produto de loja, enviando follow-ups proativos para garantir que o processo (formulário, configuração, entrega) seja concluído antes do prazo de reembolso expirar.

Sem acompanhamento proativo, esse fluxo vira reembolso — o aluno fica perdido e pede o dinheiro de volta antes de conseguir usar o produto.

**Resumo do fluxo:**
```
Webhook de compra (produto Loja Express)
  → D+0: confirma recebimento + envia passo a passo do formulário
    → Scheduler agenda D+1, D+3, D+5, D+7
      → D+1: verifica formulário → se pendente, reenvia lembrete (template)
        → D+3: verifica status da loja → informa progresso (template)
          → D+5: se loja não entregue → verifica bloqueio, aciona operação (escalação silenciosa)
            → D+7: prazo crítico → resolve ou escala com urgência
```

---

## 2. Escopo

### O que faz

- Subgraph LangGraph proativo, acionado pelo job `ProcessPurchaseWebhook` quando produto é Loja Express
- D+0: confirma recebimento da compra + envia passo a passo do formulário
- Agenda follow-ups D+1, D+3, D+5, D+7 via `scheduled_jobs`
- D+1: verifica se formulário foi respondido → lembrete via template `loja_express_d1` se pendente
- D+3: verifica status da loja → informa progresso via template `loja_express_d3`
- D+5: se loja não entregue → escalação silenciosa para operação
- D+7: prazo crítico → resolve ou escala com urgência via template `loja_express_d7`
- Cancela follow-ups pendentes quando objetivo atingido (`loja_entregue = True`)

### O que NÃO faz

- Não implementa integração de verificação de formulário — stub com TODO (CQ-L01)
- Não implementa integração de status da loja — stub com TODO (CQ-L02)
- Não define templates Meta — conteúdo a confirmar (CQ-W04, CQ-L03)
- Não gerencia idle/timeout — Core cuida
- Não processa reembolso — Spec ④

---

## 3. Arquivos

### Novos
```
src/nexoia/application/capabilities/loja_express.py
src/nexoia/domain/entities/loja_express_case.py
src/nexoia/domain/ports/loja_express_port.py        # interface para verificar formulário e status
src/nexoia/infrastructure/loja_express/client.py    # stub LojaExpressClient
src/nexoia/infrastructure/db/repositories/loja_express_case_repo.py
migrations/xxxx_add_loja_express_cases_table.py
tests/unit/capabilities/test_loja_express.py
tests/integration/test_loja_express_flow.py
```

### Modificados
```
src/nexoia/interface/worker/handlers/handle_process_purchase_webhook.py  # detecta produto Loja Express
src/nexoia/config/settings.py                       # + LOJA_EXPRESS_PRODUCT_TAGS
docs/superpowers/OPEN_QUESTIONS.md                  # + CQ-L01, CQ-L02, CQ-L03
```

---

## 4. Subgraph LangGraph

### Grafo de nós (D+0)

```
START (job ProcessPurchaseWebhook — produto Loja Express)
  │
  ▼
send_d0             ← confirma recebimento + envia passo a passo do formulário
  │
  ▼
schedule_followups  ← agenda D+1, D+3, D+5, D+7 em scheduled_jobs
  │
  ▼
persist_case        ← cria LojaExpressCase(status=AGUARDANDO_FORMULARIO)
  │
  ▼
END
```

### Grafo de nós (follow-ups — jobs agendados)

```
START (job SendScheduledFollowUp — tipo LOJA_EXPRESS_D1/D3/D5/D7)
  │
  ▼
check_case          ← carrega LojaExpressCase; se loja_entregue=True → cancela e END
  │
  ▼
execute_followup    ← lógica específica do dia (D+1/D+3/D+5/D+7)
  │
  ▼
update_case         ← atualiza status e last_followup_at
  │
  ▼
END
```

### Lógica por dia

**D+1 (`LOJA_EXPRESS_D1`):**
1. Chama `LojaExpressPort.is_form_submitted(loja_express_case_id)` → stub (TODO CQ-L01)
2. Se `False`: envia template `loja_express_d1` (lembrete de formulário)
3. Atualiza `status = LEMBRETE_D1_ENVIADO`

**D+3 (`LOJA_EXPRESS_D3`):**
1. Chama `LojaExpressPort.get_store_status(loja_express_case_id)` → stub (TODO CQ-L02)
2. Envia template `loja_express_d3` com progresso
3. Atualiza `status = CHECK_D3_ENVIADO`

**D+5 (`LOJA_EXPRESS_D5`):**
1. Chama `LojaExpressPort.get_store_status(loja_express_case_id)` → stub (TODO CQ-L02)
2. Se loja não entregue: escalação silenciosa para operação (`transfer_to_human(reason="loja_express_d5_bloqueio")`)
3. Envia mensagem (template ou texto livre — TODO CQ-L03)
4. Atualiza `status = ALERTA_D5_ENVIADO`

**D+7 (`LOJA_EXPRESS_D7`):**
1. Prazo crítico — último dia do prazo de reembolso CDC
2. Envia template `loja_express_d7` (urgência)
3. Se não resolvido: escalação silenciosa para operação
4. Atualiza `status = PRAZO_CRITICO_D7`

### Estado do subgraph

```python
class LojaExpressState(ConversationState):
    loja_express_case_id: str | None
    purchase_id: str
    student_name: str
    student_email: str
    student_phone: str
    product_name: str
    form_submitted: bool              # TODO CQ-L01 — preenchido pelo LojaExpressPort
    loja_entregue: bool               # True = objetivo atingido, cancela follow-ups
    last_followup_day: int | None     # 1, 3, 5 ou 7
    scheduled_job_ids: dict[str, str] # {"d1": job_id, "d3": job_id, ...}
```

---

## 5. Entidade e Modelo de Dados

### `LojaExpressCase`

```python
@dataclass
class LojaExpressCase:
    id: str                          # UUID
    account_id: int
    contact_id: str
    conversation_id: str
    purchase_id: str                 # idempotência
    product_name: str
    student_email: str
    form_submitted: bool             # formulário respondido
    loja_entregue: bool              # loja configurada e entregue
    status: LojaExpressCaseStatus
    scheduled_job_d1_id: str | None
    scheduled_job_d3_id: str | None
    scheduled_job_d5_id: str | None
    scheduled_job_d7_id: str | None
    created_at: datetime
    updated_at: datetime
```

### `LojaExpressCaseStatus`

```python
class LojaExpressCaseStatus(str, Enum):
    AGUARDANDO_FORMULARIO = "aguardando_formulario"
    LEMBRETE_D1_ENVIADO   = "lembrete_d1_enviado"
    CHECK_D3_ENVIADO      = "check_d3_enviado"
    ALERTA_D5_ENVIADO     = "alerta_d5_enviado"
    PRAZO_CRITICO_D7      = "prazo_critico_d7"
    ENTREGUE              = "entregue"           # objetivo atingido
    ESCALADO              = "escalado"           # operação acionada
```

### Tabela `loja_express_cases`

```sql
CREATE TABLE loja_express_cases (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id            INTEGER NOT NULL,
    contact_id            TEXT NOT NULL,
    conversation_id       TEXT NOT NULL,
    purchase_id           TEXT NOT NULL UNIQUE,
    product_name          TEXT NOT NULL,
    student_email         TEXT NOT NULL,
    form_submitted        BOOLEAN NOT NULL DEFAULT FALSE,
    loja_entregue         BOOLEAN NOT NULL DEFAULT FALSE,
    status                TEXT NOT NULL DEFAULT 'aguardando_formulario',
    scheduled_job_d1_id   TEXT,
    scheduled_job_d3_id   TEXT,
    scheduled_job_d5_id   TEXT,
    scheduled_job_d7_id   TEXT,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_loja_express_cases_account_contact ON loja_express_cases(account_id, contact_id);
CREATE INDEX idx_loja_express_cases_purchase_id ON loja_express_cases(purchase_id);
```

### Novos tipos de job em `scheduled_jobs`

```python
class JobType(str, Enum):
    # existentes
    IDLE_PING               = "IDLE_PING"
    IDLE_CLOSE              = "IDLE_CLOSE"
    FOLLOWUP_D1             = "FOLLOWUP_D1"             # Welcome reminder
    FOLLOWUP_CUSTOM         = "FOLLOWUP_CUSTOM"
    # novos (spec ⑤)
    LOJA_EXPRESS_D1         = "LOJA_EXPRESS_D1"
    LOJA_EXPRESS_D3         = "LOJA_EXPRESS_D3"
    LOJA_EXPRESS_D5         = "LOJA_EXPRESS_D5"
    LOJA_EXPRESS_D7         = "LOJA_EXPRESS_D7"
```

---

## 6. Port e Adapter (stubs)

### `LojaExpressPort`

```python
class LojaExpressPort(Protocol):
    async def is_form_submitted(self, case_id: str) -> bool: ...
    async def get_store_status(self, case_id: str) -> LojaExpressStatus: ...
```

### `LojaExpressClient` (stub)

```python
# ⚠️  TODO CQ-L01: implementar verificação de formulário quando definido o sistema
# ⚠️  TODO CQ-L02: implementar verificação de status da loja (planilha? fornecedor? API?)
class LojaExpressClient:
    async def is_form_submitted(self, case_id: str) -> bool:
        raise NotImplementedError("LojaExpressClient não implementado — ver CQ-L01")

    async def get_store_status(self, case_id: str) -> LojaExpressStatus:
        raise NotImplementedError("LojaExpressClient não implementado — ver CQ-L02")
```

---

## 7. Detecção de produto Loja Express

O handler `handle_process_purchase_webhook.py` detecta se o produto é Loja Express via configuração:

```python
LOJA_EXPRESS_PRODUCT_TAGS: list[str] = ["loja_express", "loja-express"]
# Comparação case-insensitive com product_name do webhook
```

Se detectado como Loja Express: invoca subgraph `LojaExpressCapability` em vez de `WelcomeCapability`.

---

## 8. Configuração

```python
LOJA_EXPRESS_PRODUCT_TAGS: list[str] = ["loja_express"]  # tags que identificam produto
LOJA_EXPRESS_D1_DELAY_HOURS: int = 24
LOJA_EXPRESS_D3_DELAY_HOURS: int = 72
LOJA_EXPRESS_D5_DELAY_HOURS: int = 120
LOJA_EXPRESS_D7_DELAY_HOURS: int = 168
```

---

## 9. Observabilidade

### Logs estruturados

Cada nó loga: `capability=loja_express`, `node`, `account_id`, `case_id`, `day`

- D+0 enviado → `level=INFO`, `scheduled_jobs_count=4`
- Follow-up enviado → `level=INFO`, `day`, `template`
- Formulário pendente → `level=INFO`, `day=1`, `form_submitted=False`
- D+5/D+7 escalação → `level=WARNING`, `reason=loja_not_delivered`
- Objetivo atingido → `level=INFO`, `loja_entregue=True`, `cancelled_jobs`

### Métricas Prometheus

```
loja_express_total{status="delivered"|"escalated"|"timeout"}
loja_express_followup_sent_total{day="1"|"3"|"5"|"7"}
loja_express_form_pending_at_d1_total
```

---

## 10. Testes

### Unitários (`tests/unit/capabilities/test_loja_express.py`)

| Teste | Cenário |
|-------|---------|
| `test_d0_sends_welcome_and_schedules` | D+0 → mensagem enviada + 4 jobs agendados |
| `test_d1_form_pending_sends_reminder` | D+1 + form não respondido → lembrete enviado |
| `test_d1_form_submitted_no_reminder` | D+1 + form respondido → sem mensagem |
| `test_d3_sends_progress` | D+3 → mensagem de progresso enviada |
| `test_d5_escalates_if_not_delivered` | D+5 + loja não entregue → handoff silencioso |
| `test_d7_sends_urgent_template` | D+7 → template urgente + escalação |
| `test_cancels_followups_on_delivery` | `loja_entregue=True` → todos os jobs cancelados |

### Integração (`tests/integration/test_loja_express_flow.py`)

- `FakeLojaExpressClient` como adapter de teste
- Valida `LojaExpressCase` persistido no PostgreSQL (testcontainers)
- Valida 4 jobs agendados em `scheduled_jobs`
- Valida cancelamento de jobs quando `loja_entregue=True`

---

## 11. Requisitos Funcionais

| ID | Requisito |
|----|-----------|
| `RF-L01` | Detecta produto Loja Express pelo `product_name` via `LOJA_EXPRESS_PRODUCT_TAGS`. |
| `RF-L02` | D+0: confirma recebimento + envia passo a passo do formulário. Agenda D+1/D+3/D+5/D+7. |
| `RF-L03` | D+1: verifica formulário via `LojaExpressPort`. Se pendente: template `loja_express_d1`. |
| `RF-L04` | D+3: verifica status da loja. Envia progresso via template `loja_express_d3`. |
| `RF-L05` | D+5: se loja não entregue → escalação silenciosa para operação. TODO CQ-L03 (template ou texto livre). |
| `RF-L06` | D+7: prazo crítico → template `loja_express_d7` + escalação se não resolvido. |
| `RF-L07` | Cancela todos os follow-ups pendentes quando `loja_entregue=True`. |
| `RF-L08` | Templates Meta D+1/D+3/D+7: conteúdo a confirmar — ver CQ-W04. |
| `RF-L09` | Formulário e status da loja: integração "a definir por tenant" — ver CQ-L01, CQ-L02. |

## 12. Requisitos Não-Funcionais

| ID | Requisito |
|----|-----------|
| `RNF-L01` | Tenant isolation: toda query filtra por `account_id`. |
| `RNF-L02` | Idempotência: `purchase_id UNIQUE` evita dois casos para a mesma compra. |
| `RNF-L03` | Follow-ups usam o Scheduler do Core — durável mesmo em restart. |
| `RNF-L04` | Compliance Meta: D+1/D+3/D+7 são proativos → sempre via template aprovado. |
| `RNF-L05` | Cobertura de testes: ≥90% nas linhas da capability. |
