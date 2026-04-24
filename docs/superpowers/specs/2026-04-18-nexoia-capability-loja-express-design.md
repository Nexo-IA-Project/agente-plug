# Spec ⑤ — Capability Loja Express

**Data:** 2026-04-18
**Fase:** 1
**Repositório alvo:** `nexoia-agent`
**Depende de:** Spec ① (Core — Scheduler, PurchaseHandler, ChatNexoPort)
**Status:** Design aprovado — aguardando plano de implementação

---

## 1. Contexto e Objetivo

A Capability Loja Express acompanha o aluno durante os 7 dias após a compra de um produto de loja, enviando follow-ups proativos para garantir que o processo (formulário, configuração, entrega) seja concluído antes do prazo de reembolso expirar.

Sem acompanhamento proativo, esse fluxo vira reembolso — o aluno fica perdido e pede o dinheiro de volta antes de conseguir usar o produto.

**Resumo do fluxo:**
```
Webhook de compra (produto Loja Express)
  → PurchaseHandler detecta produto Loja Express
    → CriarCasoLojaExpress.execute() — cria LojaExpressCase + agenda D+1/D+3/D+5/D+7
      → D+0: envia confirmação + passo a passo do formulário (template)
        → Worker job LOJA_EXPRESS_D1 → EnviarFollowup.execute(day=1)
          → Worker job LOJA_EXPRESS_D3 → EnviarFollowup.execute(day=3)
            → Worker job LOJA_EXPRESS_D5 → EnviarFollowup.execute(day=5) + escala se não entregue
              → Worker job LOJA_EXPRESS_D7 → EnviarFollowup.execute(day=7) + escala urgente
```

---

## 2. Escopo

### O que faz

- Capability 100% proativa — sem skill `@tool`, sem orquestração LLM. Todos os fluxos são worker-driven.
- `PurchaseHandler` (Core) detecta produto Loja Express e chama `CriarCasoLojaExpress.execute()`
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
src/nexoia/application/use_cases/loja_express/
    criar_caso.py          # cria LojaExpressCase + agenda jobs D+1/D+3/D+5/D+7
    enviar_followup.py     # lógica por dia (day=1|3|5|7): verifica status + envia template + escala
    marcar_entregue.py     # cancela jobs pendentes quando loja_entregue=True
src/nexoia/domain/entities/loja_express_case.py
src/nexoia/domain/ports/loja_express_port.py        # LojaExpressPort (formulário + status da loja)
src/nexoia/infrastructure/loja_express/client.py    # stub LojaExpressClient
src/nexoia/infrastructure/db/repositories/loja_express_case_repo.py
migrations/xxxx_add_loja_express_cases_table.py
tests/unit/use_cases/test_loja_express.py
tests/integration/test_loja_express_flow.py
```

### Modificados
```
src/nexoia/application/purchase_handler.py          # detecta produto Loja Express, chama CriarCaso
src/nexoia/interface/worker/handlers/scheduled.py   # + handlers LOJA_EXPRESS_D1/D3/D5/D7
src/nexoia/config/settings.py                       # + LOJA_EXPRESS_PRODUCT_TAGS
docs/superpowers/OPEN_QUESTIONS.md                  # + CQ-L01, CQ-L02, CQ-L03
```

---

## 4. Use Cases

Sem subgraph LangGraph. Sem skill `@tool`. Sem orquestração LLM. Fluxos inteiramente
worker-driven — use cases chamados diretamente pelos handlers do scheduler.
Estado persistido em `LojaExpressCase` no banco — sem estado no grafo.

### `CriarCasoLojaExpress` (`application/use_cases/loja_express/criar_caso.py`)

Chamado por `PurchaseHandler` quando detecta produto Loja Express (via `LOJA_EXPRESS_PRODUCT_TAGS`).

1. Cria `LojaExpressCase(status=AGUARDANDO_FORMULARIO)` — `purchase_id UNIQUE` garante idempotência
2. Envia template D+0 via `ChatNexoPort.send_template("loja_express_d0", {nome, produto})`
3. Agenda jobs: `LOJA_EXPRESS_D1` (+24h), `D3` (+72h), `D5` (+120h), `D7` (+168h)
4. Salva `scheduled_job_d1_id`, `d3_id`, `d5_id`, `d7_id` no `LojaExpressCase`

### `EnviarFollowup` (`application/use_cases/loja_express/enviar_followup.py`)

Chamado pelo worker handler em cada job agendado. Recebe `day: int` (1, 3, 5 ou 7).

**Guard de saída:** se `loja_entregue=True` → cancela jobs pendentes e retorna sem envio.

**D+1:**
1. `LojaExpressPort.is_form_submitted(case_id)` — stub TODO CQ-L01
2. Se pendente: `ChatNexoPort.send_template("loja_express_d1", ...)`
3. Atualiza `status=LEMBRETE_D1_ENVIADO`

**D+3:**
1. `LojaExpressPort.get_store_status(case_id)` — stub TODO CQ-L02
2. `ChatNexoPort.send_template("loja_express_d3", {progresso})`
3. Atualiza `status=CHECK_D3_ENVIADO`

**D+5:**
1. `LojaExpressPort.get_store_status(case_id)` — stub TODO CQ-L02
2. Se loja não entregue: `ChatNexoPort.transfer_to_human(reason="loja_express_d5_bloqueio")`
3. Envia template ou texto livre — TODO CQ-L03
4. Atualiza `status=ALERTA_D5_ENVIADO`

**D+7:**
1. `ChatNexoPort.send_template("loja_express_d7", ...)` — urgência, último dia CDC
2. `ChatNexoPort.transfer_to_human(reason="loja_express_d7_prazo_critico")`
3. Atualiza `status=PRAZO_CRITICO_D7`

### `MarcarEntregue` (`application/use_cases/loja_express/marcar_entregue.py`)

Pode ser chamado por integração futura ou operador via admin. Seta `loja_entregue=True`
e cancela jobs `D+X` pendentes via `SchedulerPort.cancel(job_id)`.

### Detecção de produto Loja Express

Em `PurchaseHandler.execute()` — verifica `event.product_name` contra `LOJA_EXPRESS_PRODUCT_TAGS`
(comparação case-insensitive). Se detectado: chama `CriarCasoLojaExpress` em vez do fluxo Welcome padrão.

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

`PurchaseHandler.execute()` verifica `event.product_name` contra `LOJA_EXPRESS_PRODUCT_TAGS`
(comparação case-insensitive). Configuração:

```python
LOJA_EXPRESS_PRODUCT_TAGS: list[str] = ["loja_express", "loja-express"]
```

Se detectado: chama `CriarCasoLojaExpress.execute(event)` em vez do fluxo Welcome padrão.
Sem LangGraph envolvido — é Python puro.

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

### Unitários (`tests/unit/use_cases/test_loja_express.py`)

| Teste | Cenário |
|-------|---------|
| `test_criar_caso_d0_sends_template_and_schedules` | D+0 → template enviado + 4 jobs agendados |
| `test_d1_form_pending_sends_reminder` | D+1 + form pendente → lembrete enviado |
| `test_d1_form_submitted_no_message` | D+1 + form respondido → sem mensagem |
| `test_d3_sends_progress` | D+3 → template de progresso enviado |
| `test_d5_escalates_if_not_delivered` | D+5 + loja não entregue → transfer_to_human |
| `test_d7_sends_urgent_template_and_escalates` | D+7 → template urgente + transfer_to_human |
| `test_guard_skips_if_delivered` | `loja_entregue=True` em qualquer D+X → nenhuma ação |
| `test_marcar_entregue_cancels_jobs` | `MarcarEntregue.execute()` → jobs pendentes cancelados |

### Integração (`tests/integration/test_loja_express_flow.py`)

- `FakeLojaExpressClient` e `FakeChatNexoClient` como adapters
- Valida `LojaExpressCase` persistido no PostgreSQL (testcontainers)
- Valida 4 jobs agendados em `scheduled_jobs`
- Valida idempotência: segunda compra com mesmo `purchase_id` não cria caso duplicado

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
