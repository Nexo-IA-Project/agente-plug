# NexoIA — Follow-up Engine v2: Webhook Hubla, Smart Re-sync, Memória de IA e Relatórios

**Data:** 2026-05-21
**Status:** Draft (aguardando review do usuário)
**Subsistema:** C+ — Follow-up Engine (evolução da spec de 2026-05-07)
**Depende de:** Spec ① Core, Spec ② Welcome, Spec C — Follow-up Engine, Spec — Dynamic Followup by Course

---

## Visão Geral

Esta v2 fecha as lacunas críticas do Follow-up Engine atual: processamento robusto do webhook Hubla (`subscription.activated`), re-sincronização automática de enrollments ativos quando um flow é editado, memória de IA configurável por conta e endpoints de relatório de enrollments. Mantém Clean Architecture + SOLID — todas as mudanças passam por use cases isolados, com ports/adapters explícitos.

**Não-objetivos:** A/B testing, suporte a outros provedores além de Hubla, métricas de engajamento (abertura/clique), UI de relatórios (apenas API), notificação push para admin.

---

## Decisões de Design (consolidadas do brainstorming)

| # | Decisão | Racional |
|---|---------|----------|
| D1 | Webhook `/webhook/purchase` passa a aceitar **somente** o formato Hubla v2.0.0 aninhado (`event.subscription`, `event.products[]`). Formato flat antigo é substituído. | Não há clientes legados em produção; reduz complexidade do parser. |
| D2 | `ai_memory_messages` é aplicado **apenas na leitura** do histórico. O JSONB `messages` persiste tudo; o dispatcher pega só os últimos N ao montar contexto do LLM. | Operador pode reconfigurar dinamicamente; histórico preservado para auditoria. |
| D3 | Cancelar/reagendar step PENDING usa **coluna `scheduled_job_id`** em `followup_enrollment_steps`. Re-sync atualiza `scheduled_jobs.status='cancelled'` no job antigo e cria novo. | Rastreio explícito, auditável. Custo: 1 coluna nullable. |
| D4 | DLQ não recebe expansão de escopo. Apenas garantir que steps com `status=FAILED` carreguem `failure_reason` e que o caminho de retry → DLQ (já existente em `WorkerDispatcher`) funcione. | Infra DLQ já completa; basta tratamento explícito no dispatch. |

---

## Requisitos Funcionais

### 5.1 Webhook Hubla v2

| # | Requisito |
|---|-----------|
| RF-W01 | `POST /webhook/purchase` aceita payload `subscription.activated` (versão 2.0.0) e retorna `202` em < 200ms. |
| RF-W02 | Dedup do webhook continua via `WebhookEvent` (Redis 24h TTL) usando `event.subscription.id` como `purchase_id`. |
| RF-W03 | O handler itera `event.products[]`; para cada produto, busca `Course` ativo por `hubla_id = product.id` e enfileira processamento. |
| RF-W04 | Se nenhum `Course` for encontrado para um `product.id`: logar warning estruturado e ignorar **aquele produto** (não falhar o webhook). |
| RF-W05 | Para cada produto com Course válido: cria/atualiza `Contact` por phone do `payer`, recupera/cria `Conversation` ativa, dispara welcome (comportamento atual) e enfileira enrollment em todos os `FollowupFlow` ativos do curso. |
| RF-W06 | `EnrollContactUseCase` é chamado com `purchase_time = event.subscription.activatedAt`, `purchase_id = event.subscription.id`. |

### 5.2 Deduplicação e Integridade

| # | Requisito |
|---|-----------|
| RF-D01 | UNIQUE constraint `(account_id, contact_id, flow_id, purchase_id)` em `followup_enrollments`. Tentativa duplicada → ignora silenciosamente e loga. |
| RF-D02 | `followup_enrollments.flow_id` recebe `FOREIGN KEY → followup_flows(id) ON DELETE SET NULL` (histórico preservado). |
| RF-D03 | `EnrollContactUseCase` executa criação de enrollment + steps + agendamento de jobs em **uma única transação**. Falha parcial → rollback completo. |
| RF-D04 | Novo campo `followup_enrollment_steps.failure_reason TEXT NULL`. |
| RF-D05 | Novo campo `followup_enrollment_steps.scheduled_job_id UUID NULL` (FK fraca → scheduled_jobs.id; sem constraint para permitir cleanup independente). |
| RF-D06 | Novo campo `followup_enrollment_steps.flow_step_id UUID NULL` (FK fraca → followup_steps.id; identidade do step no diff de re-sync). |
| RF-D07 | Índices: `(flow_id, status)`, `(account_id, contact_id)` em enrollments; `(enrollment_id, status)` em steps. |

### 5.3 Smart Re-sync de Enrollments

| # | Requisito |
|---|-----------|
| RF-R01 | Toda mutação de step em um flow (POST/PUT/DELETE em `/admin/followup/flows/{id}/steps`, reorder) enfileira job `kind="resync_flow"` com `{flow_id, account_id}` após commit. |
| RF-R02 | Worker handler `handle_resync_flow` carrega o flow + steps atuais, lista enrollments com `status='active'`, e processa cada um via `ResyncEnrollmentUseCase.execute(enrollment_id)`. |
| RF-R03 | `ResyncEnrollmentUseCase` por enrollment: diff entre `flow.steps` (atual) e `enrollment.steps` (existente) usando `flow_step_id` (UUID do step no flow) como identidade. Aplica: **(a)** step novo no flow → criar `FollowupEnrollmentStep` PENDING + agendar `scheduled_job` + salvar `scheduled_job_id`; **(b)** delay alterado em step PENDING → cancelar `scheduled_job` antigo (UPDATE status='cancelled'), criar novo, atualizar `scheduled_job_id` no enrollment_step; **(c)** conteúdo alterado (template_name, message_text, template_variables) em step PENDING → atualizar snapshot no `enrollment_step` in-place, **sem cancelar o job** (mantém o mesmo `scheduled_job_id`); **(d)** step removido do flow e ainda PENDING → marcar `enrollment_step` como `CANCELLED` e cancelar `scheduled_job`; **(e)** steps com `status=SENT`, `FAILED` ou `CANCELLED` nunca são modificados. |
| RF-R04 | Re-sync é **idempotente**: a comparação usa `flow_step_id` como chave estável e compara `delay`/conteúdo por igualdade. Re-execução com mesmo estado produz `Diff` vazio. |
| RF-R05 | `followup_enrollment_steps` ganha coluna `flow_step_id UUID NULL` (FK fraca para `followup_steps.id`) que serve como identidade do step no diff. Para enrollments criados antes desta v2, o re-sync os trata como "imutáveis" (skip total, log warning). |
| RF-R06 | Falha de re-sync em um enrollment não interrompe os demais. Cada enrollment é uma sub-transação isolada; falhas são logadas com `enrollment_id`. |
| RF-R07 | Re-sync é registrado em `audit_events` com `action='flow_resynced'` e payload `{flow_id, enrollments_affected, steps_added, steps_cancelled, steps_rescheduled, steps_content_updated}`. |
| RF-R08 | Status `CANCELLED` é adicionado ao enum `EnrollmentStepStatus` (`PENDING | SENT | FAILED | CANCELLED`). |

### 5.4 Memória de IA Configurável

| # | Requisito |
|---|-----------|
| RF-M01 | `AccountSettings` ganha campo `ai_memory_messages: int` (default 20, range 5–100). Armazenado no JSONB `accounts.settings`. Sem migration de schema. |
| RF-M02 | `MessageDispatcher`, ao montar contexto, lê `AccountSettings.ai_memory_messages` do DB e passa como `limit` para o histórico. |
| RF-M03 | `ConversationHistory.load(thread_id, limit: int \| None = None)` aceita limit; quando informado, retorna as últimas N mensagens do JSONB (slice). Sem limit → retorna tudo (compat). |
| RF-M04 | A escrita continua acumulando todas as mensagens no JSONB (sem trim). |
| RF-M05 | `GET/PUT /admin/settings` expõe `ai_memory_messages` no schema; validação Pydantic com `ge=5, le=100`. |
| RF-M06 | UI `/admin/settings` exibe input numérico "Memória da IA (últimas N mensagens)" com hint do range. |

### 5.5 Dispatch Robusto

| # | Requisito |
|---|-----------|
| RF-X01 | `DispatchFollowupStepUseCase` captura exceções de `chatnexo.send_template` e `chatnexo.send_message`. Em falha: marca step como `FAILED`, salva `failure_reason` (mensagem da exceção truncada a 500 chars), retorna `DispatchResult(status='FAILED', reason=...)`. |
| RF-X02 | O worker handler de `followup_step` não propaga exceção quando o use case retorna `FAILED` — o job termina como sucesso (do ponto de vista da fila). O erro fica visível no `enrollment_step`. |
| RF-X03 | Falhas de infraestrutura (DB indisponível, OOM) continuam propagando; o `WorkerDispatcher` aplica retry/DLQ como já faz. |

### 5.6 Relatórios

| # | Requisito |
|---|-----------|
| RF-L01 | `GET /admin/followup/enrollments` com filtros `flow_id`, `contact_phone`, `status`, paginação (`page`, `page_size` default 20 max 100). |
| RF-L02 | Resposta inclui por item: `id, contact_phone, customer_name, flow_id, flow_name, course_name, status, created_at, steps_sent, steps_total`. |
| RF-L03 | `GET /admin/followup/enrollments/{enrollment_id}/steps` retorna lista ordenada por `position` com `status, template_name, message_text_preview (primeiros 80 chars), sent_at, scheduled_for, failure_reason`. |
| RF-L04 | `GET /admin/followup/flows` é atualizado para incluir bloco `stats: {enrollments_active, enrollments_completed}` por flow. |
| RF-L05 | Listagem de 1000 enrollments < 500ms com os índices criados em RF-D06. |

---

## Arquitetura

### Camadas afetadas

```
interface/http/routers/admin/
  followup.py                       ← + trigger de resync no POST/PUT/DELETE/reorder de step
                                    ← + stats no GET /flows
  followup_enrollments.py           ← NOVO (RF-L01, RF-L03)
  settings.py                       ← + campo ai_memory_messages (RF-M05)
  webhook_purchase.py               ← parser do payload Hubla v2 (RF-W01..W06)

interface/worker/handlers/
  scheduled.py                      ← + handler 'resync_flow' (RF-R02)
  message.py / purchase.py          ← purchase usa payload aninhado

shared/application/
  message_dispatcher.py             ← lê ai_memory_messages (RF-M02)
  purchase_handler.py               ← itera event.products[] (RF-W03..W06)
  use_cases/followup/
    enroll_contact.py               ← dedup (RF-D01), transação atômica (RF-D03)
    dispatch_followup_step.py       ← failure handling (RF-X01)
    resync_enrollment.py            ← NOVO (RF-R03..R05)

shared/agent/
  history.py                        ← load() aceita limit (RF-M03)

shared/adapters/db/
  models.py                         ← failure_reason + scheduled_job_id em step;
                                      enum CANCELLED; índices
  repositories/
    followup_enrollment_repo.py     ← list_with_filters, count_by_status,
                                      find_active_by_flow, cancel_step,
                                      bulk_create_steps
    followup_flow_repo.py           ← trigger de re-sync após mutação de step
    account_settings_repo.py        ← getter validado de ai_memory_messages

shared/domain/
  entities/followup.py              ← + EnrollmentStepStatus.CANCELLED
                                    ← + failure_reason, scheduled_job_id
  ports/                             ← (sem novos ports — re-sync é use case puro)

migrations/versions/
  XXXX_followup_engine_v2.py        ← FK, índices, failure_reason, scheduled_job_id,
                                      novo valor de enum
```

### Fluxo: Webhook Hubla v2

```
POST /webhook/purchase
  → valida HUBLA_WEBHOOK_SECRET
  → WebhookEventRepo (dedup por event.subscription.id)
  → enqueue job kind="purchase", payload = raw event
  → 202 Accepted

worker.handle_purchase(payload):
  → para cada product in event.products:
      → course = course_repo.find_active_by_hubla_id(product.id)
      → se None: log warning, continue
      → contact = contact_repo.upsert_by_phone(payer.phone, payer)
      → conversation = conversation_repo.get_or_create_active(contact)
      → access_case + welcome (comportamento atual)
      → flows = followup_flow_repo.list_active_by_course(course.id)
      → para cada flow:
          → EnrollContactUseCase.execute(
              contact, conversation, flow,
              purchase_time=event.subscription.activatedAt,
              purchase_id=event.subscription.id,
            )
```

### Fluxo: Re-sync

```
PUT /admin/followup/flows/{id}/steps/{step_id}
  → followup_flow_repo.update_step(...)
  → COMMIT
  → enqueue job kind="resync_flow", payload={flow_id, account_id}
  → 200 OK

worker.handle_resync_flow(payload):
  → enrollments = followup_enrollment_repo.find_active_by_flow(flow_id)
  → flow_steps = followup_step_repo.list_by_flow(flow_id)
  → audit = {steps_added: 0, steps_cancelled: 0, steps_rescheduled: 0,
             steps_content_updated: 0, enrollments_affected: 0}
  → para cada enrollment in enrollments (sub-transação por enrollment):
      → diff = compute_diff(flow_steps, enrollment.steps)
      → para flow_step em diff.to_add:
          → step = bulk_create_steps([flow_step], enrollment)  # com flow_step_id
          → job_id = scheduled_jobs.enqueue(FOLLOWUP_STEP, run_at=..., payload={step.id})
          → step.scheduled_job_id = job_id
          → audit.steps_added += 1
      → para (enr_step, flow_step) em diff.to_reschedule:
          → scheduled_jobs.cancel(enr_step.scheduled_job_id)
          → enr_step.apply_snapshot(flow_step)  # delay + conteúdo
          → new_job_id = scheduled_jobs.enqueue(FOLLOWUP_STEP, run_at=novo, ...)
          → enr_step.scheduled_job_id = new_job_id
          → audit.steps_rescheduled += 1
      → para (enr_step, flow_step) em diff.to_update_content:
          → enr_step.apply_snapshot(flow_step)  # só conteúdo, job intocado
          → audit.steps_content_updated += 1
      → para enr_step em diff.to_cancel:
          → scheduled_jobs.cancel(enr_step.scheduled_job_id)
          → enr_step.status = CANCELLED
          → audit.steps_cancelled += 1
      → audit.enrollments_affected += 1
  → audit_events.log(action="flow_resynced", payload=audit)
```

### Fluxo: Memória de IA

```
mensagem chega → MessageDispatcher.dispatch(conversation, msg):
  → settings = account_settings_repo.get(account_id)
  → limit = settings.ai_memory_messages  # default 20
  → history = ConversationHistory(...).load(thread_id, limit=limit)
  → contexto = build_context(history)  # já recortado
  → openai_loop(contexto, tools=...)
  → ConversationHistory.append(...)  # persiste sem trim
```

### Diff Algorithm (RF-R03/R04)

Identidade do step para diff: `flow_step_id` (UUID do `followup_steps.id`). Cada `enrollment_step` carrega esse FK para permitir comparar com o `flow.steps` atual.

```python
def compute_diff(flow_steps, enrollment_steps):
    to_add, to_reschedule, to_update_content, to_cancel = [], [], [], []

    enr_by_flow_step = {
        s.flow_step_id: s for s in enrollment_steps if s.flow_step_id is not None
    }

    for flow_step in flow_steps:
        enr = enr_by_flow_step.get(flow_step.id)
        if enr is None:
            to_add.append(flow_step)
            continue
        if enr.status != EnrollmentStepStatus.PENDING:
            continue  # SENT, FAILED, CANCELLED → imutável

        delay_changed = enr.delay_from_purchase_hours != flow_step.delay_from_purchase_hours
        content_changed = (
            enr.meta_template_name != flow_step.meta_template_name
            or enr.message_text != flow_step.message_text
            or enr.template_variables != flow_step.template_variables
        )
        if delay_changed:
            to_reschedule.append((enr, flow_step))  # content_changed também aplicado
        elif content_changed:
            to_update_content.append((enr, flow_step))

    flow_step_ids = {s.id for s in flow_steps}
    for enr in enrollment_steps:
        if (
            enr.flow_step_id is not None
            and enr.flow_step_id not in flow_step_ids
            and enr.status == EnrollmentStepStatus.PENDING
        ):
            to_cancel.append(enr)

    return Diff(to_add, to_reschedule, to_update_content, to_cancel)
```

Garante idempotência: chamadas sucessivas com mesmo estado produzem `Diff` vazio em todos os buckets.

---

## Data Model — Migration

**`XXXX_followup_engine_v2.py`** (Alembic):

```sql
-- 1. Add FK + ON DELETE SET NULL em followup_enrollments.flow_id
ALTER TABLE followup_enrollments
  ADD CONSTRAINT fk_followup_enrollments_flow
  FOREIGN KEY (flow_id) REFERENCES followup_flows(id) ON DELETE SET NULL;

-- 2. UNIQUE (account_id, contact_id, flow_id, purchase_id)
CREATE UNIQUE INDEX uq_followup_enrollment_dedup
  ON followup_enrollments(account_id, contact_id, flow_id, purchase_id);

-- 3. Índices de leitura
CREATE INDEX idx_followup_enrollments_flow_status
  ON followup_enrollments(flow_id, status);
CREATE INDEX idx_followup_enrollments_account_contact
  ON followup_enrollments(account_id, contact_id);
CREATE INDEX idx_followup_enrollment_steps_enr_status
  ON followup_enrollment_steps(enrollment_id, status);

-- 4. Novos campos em followup_enrollment_steps
ALTER TABLE followup_enrollment_steps
  ADD COLUMN failure_reason TEXT NULL,
  ADD COLUMN scheduled_job_id UUID NULL,
  ADD COLUMN flow_step_id UUID NULL;

-- Para enrollments antigos (sem flow_step_id), o re-sync os trata como imutáveis.
-- Não há backfill automático: histórico anterior à v2 permanece estático.

-- 5. Novo valor no enum EnrollmentStepStatus
ALTER TYPE enrollment_step_status ADD VALUE IF NOT EXISTS 'CANCELLED';
```

Notas:
- O cancelamento do `scheduled_job` é via `UPDATE scheduled_jobs SET status='cancelled'`; o worker já ignora jobs cancelados (verificar `WorkerDispatcher.fetch_due()` — incluir cláusula `status='pending'`).
- Backfill não necessário: campos novos são nullable; dedup index é seguro porque não há duplicatas históricas (purchase_id é UUID único).

---

## API Changes

### Atualizado: `POST /webhook/purchase`

Aceita exclusivamente o payload Hubla v2:

```jsonc
{
  "type": "subscription.activated",
  "version": "2.0.0",
  "event": {
    "product": { "id": "...", "name": "..." },
    "products": [{ "id": "...", "name": "...", "offers": [...] }],
    "subscription": {
      "id": "uuid",
      "payer": {
        "firstName": "...", "lastName": "...",
        "document": "...", "email": "...", "phone": "+55..."
      },
      "activatedAt": "2026-05-02T02:59:25.256Z",
      "status": "active"
    },
    "user": { "id": "...", "email": "...", "phone": "+55..." }
  }
}
```

Resposta: `202 Accepted` (mesmo do atual). Erros de schema → `422`.

### Novo: `GET /admin/followup/enrollments`

```
Query: flow_id?, contact_phone?, status?, page=1, page_size=20

Response 200:
{
  "items": [{
    "id": "uuid", "contact_phone": "+55...", "customer_name": "...",
    "flow_id": "uuid", "flow_name": "...", "course_name": "...",
    "status": "active", "created_at": "ISO8601",
    "steps_sent": 2, "steps_total": 7
  }],
  "total": 42, "page": 1, "page_size": 20
}
```

### Novo: `GET /admin/followup/enrollments/{id}/steps`

```
Response 200: [{
  "id": "uuid", "position": 1, "delay_from_purchase_hours": 0,
  "template_name": "...", "message_text_preview": "...",
  "status": "sent", "sent_at": "ISO8601", "scheduled_for": "ISO8601",
  "failure_reason": null
}]
```

### Atualizado: `GET /admin/followup/flows`

```
Response 200: [{
  ...campos existentes...,
  "stats": { "enrollments_active": 143, "enrollments_completed": 58 }
}]
```

### Atualizado: `GET/PUT /admin/settings`

Schema ganha `ai_memory_messages: int (default 20, 5..100)`.

---

## Requisitos Não-Funcionais

| # | Requisito |
|---|-----------|
| RNF-01 | Latência webhook `subscription.activated`: 202 em < 200ms (somente dedup + enqueue, sem trabalho pesado). |
| RNF-02 | Re-sync por enrollment: < 500ms. Lote de 1000 enrollments: < 30s (processado pelo worker em background). |
| RNF-03 | Listagem de 1000 enrollments com filtros < 500ms (validar com índices RF-D06). |
| RNF-04 | Isolamento: falha em 1 enrollment durante re-sync não cancela os demais (sub-transações independentes). |
| RNF-05 | Idempotência: re-sync executado N vezes produz o mesmo estado final. |
| RNF-06 | Observabilidade: todo enrollment, dispatch e re-sync logado com `account_id`, `flow_id`, `contact_phone`. |
| RNF-07 | Clean Architecture mantida: zero acoplamento de domain a SQLAlchemy/HTTP/Redis. |
| RNF-08 | Cobertura de testes unitários ≥ 85% em `resync_enrollment.py`, `enroll_contact.py`, `dispatch_followup_step.py`. |

---

## Out of Scope (v2)

- Eventos Hubla `subscription.canceled` / `subscription.refunded`.
- Suporte a Kiwify, Hotmart (arquitetura está extensível via parser, mas implementação futura).
- A/B testing de flows.
- Métricas de abertura/clique de mensagens WhatsApp.
- UI de visualização de relatórios (apenas API; frontend pode vir em v3).
- Notificações push para admin quando enrollment falha.
- Migration para steps históricos terem `scheduled_job_id` retroativo (campo continua NULL para steps antigos — não afeta dispatch já feito).

---

## Plano de Implementação (visão geral, detalhamento em `writing-plans`)

Ordem proposta de execução (cada bloco pode virar 1+ tasks do writing-plans):

1. **T1 — Migration + modelos**: FK, índices, `failure_reason`, `scheduled_job_id`, enum `CANCELLED`, ajustes em models/entities/repos.
2. **T2 — Webhook Hubla v2**: parser do payload aninhado, dedup com `subscription.id`, loop de `products[]`, atualização do `purchase_handler`.
3. **T3 — Enrollment robusto**: UNIQUE constraint check em `EnrollContactUseCase`, transação atômica, persistência de `scheduled_job_id`.
4. **T4 — Dispatch com error handling**: try/except em `DispatchFollowupStepUseCase`, gravação de `failure_reason`, retorno explícito.
5. **T5 — Smart Re-sync**: `ResyncEnrollmentUseCase` + diff + cancel/reagenda jobs; handler `resync_flow` no worker; trigger no router de step CRUD.
6. **T6 — Memória de IA**: campo em `AccountSettings`, parametrização do `ConversationHistory.load`, integração no `MessageDispatcher`, UI.
7. **T7 — Relatórios**: novos endpoints, métodos de repo, stats em `GET /flows`.
8. **T8 — Testes end-to-end + checkpoints manuais**: webhook → enrollment, edit de step → re-sync, settings UI → memory, listagem com filtros.

---

## Testing Strategy

**Unitários (sem DB real):**
- `ResyncEnrollmentUseCase`: 3 cenários de diff (add, reschedule, cancel) + idempotência + step `SENT` imune.
- `EnrollContactUseCase`: dedup retorna sucesso silencioso + rollback em falha parcial + persistência de `scheduled_job_id`.
- `DispatchFollowupStepUseCase`: exception path → `FAILED` + `failure_reason` salvo + sem propagação.
- `compute_diff`: snapshot tests.

**Integração (com Postgres + Redis):**
- Webhook `subscription.activated` end-to-end: POST → enrollment + steps + jobs agendados.
- Edit de step PUT → job de resync executa → enrollments ativos atualizados.
- Dispatch com template Meta inválido → step FAILED com `failure_reason`.

**Checkpoints manuais (USER TEST):**
- Webhook mock no Hubla format → enrollment criado, jobs visíveis em `scheduled_jobs`.
- Criar enrollment com 5 steps, disparar 2, adicionar 2 steps novos via UI → apenas os novos agendam, antigos preservados.
- Alterar `ai_memory_messages` para 5 no painel → próxima mensagem do agente usa só 5 últimas (verificar via log/contexto).
- Listar enrollments com filtros, validar paginação e performance.

---

## Apêndice: Métricas de Sucesso

| Métrica | Alvo |
|---------|------|
| % de `subscription.activated` que geram enrollment sem erro silencioso | 100% |
| Tempo entre save de step e re-sync de enrollments ativos | < 30s para 1000 enrollments |
| Operador altera memória da IA sem redeploy | sim |
| Listagem 1000 enrollments com filtros | < 500ms |
| Enrollments duplicados | 0 |
| Steps FAILED visíveis em `/admin/followup/enrollments/{id}/steps` | 100% |
