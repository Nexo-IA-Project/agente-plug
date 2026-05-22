# PRD: Follow-up Engine v2 — Webhook Processing, Smart Re-sync & AI Memory

**Author:** Fabio Dias
**Date:** 2026-05-21
**Status:** Draft
**Version:** 1.0
**Taskmaster Optimized:** Yes

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Problem Statement](#2-problem-statement)
3. [Goals & Success Metrics](#3-goals--success-metrics)
4. [User Stories](#4-user-stories)
5. [Functional Requirements](#5-functional-requirements)
6. [Technical Architecture](#6-technical-architecture)
7. [Data Model Changes](#7-data-model-changes)
8. [API Changes](#8-api-changes)
9. [Non-Functional Requirements](#9-non-functional-requirements)
10. [Out of Scope](#10-out-of-scope)
11. [Implementation Plan](#11-implementation-plan)
12. [Testing Strategy](#12-testing-strategy)

---

## 1. Executive Summary

O sistema já possui a infraestrutura de Follow-up Engine (fluxos, steps, enrollments, dispatch via worker). Esta v2 fecha as lacunas críticas identificadas: processamento robusto do webhook Hubla (`subscription.activated`), re-sincronização inteligente de enrollments quando um flow é editado, memória de IA configurável por conversa e relatórios de histórico de disparos. A arquitetura segue Clean Architecture + SOLID com isolamento total entre camadas.

**Escopo desta v2 (em ordem de prioridade):**
1. Webhook Hubla: processar `subscription.activated` → enroll no curso correto
2. Smart Re-sync: quando flow é editado, enrollments ativos recebem os novos steps na posição correta (respeitando o que já foi enviado)
3. Memória de IA: janela de mensagens configurável, injetada no contexto do agente
4. Relatórios: API de listagem de enrollments + histórico de dispatches
5. Correções de integridade: FKs faltantes, deduplicação, retry logic no dispatch

---

## 2. Problem Statement

### User Impact
Operadores de marketing perdem conversões porque o sistema não processa automaticamente vendas Hubla em sequências de follow-up. Clientes que compram não recebem a sequência de onboarding, reduzindo engajamento e retenção. Quando operadores editam flows existentes, compradores ativos ficam sem os novos steps — os operadores não têm como corrigir isso sem acesso técnico ao banco.

### Business Impact
Cada venda sem follow-up representa receita não capturada em upsells e engajamento. Sem relatórios de dispatch, é impossível medir o ROI da sequência de mensagens. A falta de configuração da memória de IA significa que o agente pode perder contexto ou consumir tokens desnecessários, aumentando custo operacional.

### 2.1 Processamento de Webhook

O webhook `subscription.activated` do Hubla chega com `product.id` (hubla_id). O sistema precisa:
- Localizar o `Course` correspondente pelo `hubla_id`
- Inscrever o comprador em **todos os flows ativos** do curso
- Agendar os steps conforme `delay_from_purchase_hours`
- Registrar tudo para auditoria

**Payload principal recebido:**
```json
{
  "type": "subscription.activated",
  "event": {
    "product": { "id": "QaIlGtff9tlU94JjDKSq", "name": "..." },
    "subscription": {
      "id": "uuid",
      "payer": {
        "firstName": "...", "lastName": "...",
        "document": "CPF", "email": "...", "phone": "+55..."
      },
      "activatedAt": "2026-05-02T02:59:25.256Z"
    },
    "user": { "id": "...", "email": "...", "phone": "+55..." }
  }
}
```

### 2.2 Falta de Re-sync Inteligente

Hoje, quando um flow tem seus steps alterados (adicionados, removidos, reordenados), os enrollments já ativos **não são atualizados**. O sistema precisa detectar a mudança e:
- Ignorar steps já enviados (status `SENT`)
- Adicionar ao enrollment os novos steps que ainda não foram disparados
- Respeitar a nova ordem (`position`) configurada no flow
- Não reenviar o que já foi enviado

### 2.3 Memória de IA Não Configurável

O agente de IA usa histórico de mensagens da conversa, mas o tamanho da janela de memória **não é configurável** no painel admin. Operadores precisam ajustar sem tocar no código.

### 2.4 Relatórios Inexistentes

Não há forma de consultar:
- Quais enrollments estão ativos/completos para um contato
- Quais steps foram enviados e quando
- Taxa de disparo por flow

---

## 3. Goals & Success Metrics

### SMART Goals

| Goal | Métrica de Sucesso | Prazo |
|------|-------------------|-------|
| Webhook Hubla processado | 100% dos `subscription.activated` geram enrollment sem erro silencioso | Ao lançar |
| Re-sync de flow | Enrollments ativos recebem novos steps em < 1s após save do step | Ao lançar |
| Memória de IA configurável | Operador altera janela no painel sem redeploy; reflete na próxima mensagem | Ao lançar |
| Relatórios de dispatch | API com filtros lista 1000 enrollments em < 500ms (índices corretos) | Ao lançar |
| Zero duplicatas | 0 enrollments duplicados por `(account_id, contact_id, flow_id, purchase_id)` | Ao lançar |
| Retry em dispatch falho | 100% dos steps FAILED visíveis na DLQ para requeue manual | Ao lançar |

---

## 4. User Stories

### Operador de Marketing
> Como operador, quero criar um flow de 7 steps para o curso "Máquina de Vendas: Shopee" e, quando uma venda chegar, que o sistema dispare automaticamente a sequência para o comprador.

### Operador que Edita Flow
> Como operador, depois de disparar 2 steps para 200 clientes, quero adicionar um 6º e 7º steps ao flow e que o sistema dispare esses novos steps somente para quem ainda não os recebeu, sem reenviar o que já foi.

### Operador de Suporte
> Como operador, quero ver o histórico de mensagens enviadas para um contato específico: quais steps foram disparados, quando e com qual status.

### Operador Técnico
> Como operador, quero configurar no painel que a IA use as últimas 20 mensagens de contexto (e não 10 ou 50), sem precisar de redeploy.

---

## 5. Functional Requirements

### Priority Labels
- **[P0]** Bloqueador — sem isso o sistema não funciona
- **[P1]** Alta — impacto direto em conversões
- **[P2]** Média — melhoria operacional
- **[P3]** Baixa — polish / relatório

### 5.1 Webhook Hubla — `subscription.activated`

**REQ-001** [P0]: O endpoint `POST /webhook/purchase` deve aceitar o evento `subscription.activated` (versão `2.0.0`) do Hubla e retornar 202 em < 200ms.
- Task hint: atualizar `purchase_handler.py`; adicionar parser para `subscription.id` como `purchase_id`

**REQ-002** [P0]: Ao receber o evento, o sistema deve:
1. Extrair `event.product.id` como `hubla_id`
2. Buscar `Course` ativo com `hubla_id` correspondente
3. Se não encontrado: logar warning, retornar 202 (não falhar)
4. Se encontrado: criar/atualizar `Contact` com phone, name, email do payer
5. Criar ou recuperar `Conversation` ativa para o contato
6. Buscar todos os `FollowupFlow` ativos do curso
7. Para cada flow: chamar `EnrollContactUseCase` com `purchase_time = activatedAt`
8. Criar `AccessCase` e disparar welcome template (comportamento atual mantido)
- Task hint: envolve `PurchaseHandler`, `EnrollContactUseCase`, `CourseRepository`

**REQ-003** [P1]: Deduplicação de enrollment: a combinação `(account_id, contact_id, flow_id, purchase_id)` deve ser única. Se duplicata detectada, ignorar silenciosamente e logar.
- Task hint: adicionar constraint UNIQUE na migration + check em `EnrollContactUseCase`
- Dependencies: REQ-001

**REQ-004** [P0]: O `purchase_id` deve ser extraído de `event.subscription.id` (UUID da subscription Hubla).
- Dependencies: REQ-001

**REQ-005** [P1]: Suporte a múltiplos produtos no array `event.products` — se o payload contiver mais de um produto, processar cada um separadamente.
- Task hint: loop em `event.products` no purchase handler
- Dependencies: REQ-002

---

### 5.2 Smart Re-sync de Enrollments

**REQ-006** [P0]: Sempre que um `FollowupStep` é criado, atualizado (posição/delay) ou deletado em um flow, o sistema deve disparar o processo de re-sync assíncrono para todos os enrollments ativos (`status = 'active'`) daquele flow.
- Task hint: enfileirar job `resync_flow` no `followup_flow_repo` após cada mutação de step

**REQ-007** [P0]: O processo de re-sync (`ResyncEnrollmentUseCase`) deve:
1. Carregar os steps atuais do flow (ordenados por `position`)
2. Para cada enrollment ativo:
   a. Carregar seus `FollowupEnrollmentStep` existentes
   b. Identificar steps do flow **novos** (não existem no enrollment)
   c. Identificar steps do flow que **mudaram de delay** mas ainda estão `PENDING`
   d. Para steps novos: criar `FollowupEnrollmentStep` com status `PENDING` e agendar job
   e. Para steps com delay alterado e ainda `PENDING`: cancelar job anterior, reagendar com novo timing
   f. Para steps deletados do flow que ainda estão `PENDING`: marcar como `CANCELLED`
   g. Steps já `SENT` nunca são modificados
- Task hint: novo arquivo `resync_enrollment.py` em `use_cases/followup/`
- Dependencies: REQ-006, T1 (migration com FK e índices)

**REQ-008** [P1]: O re-sync deve ser idempotente — executar N vezes produz o mesmo resultado.
- Task hint: checar se step já existe no enrollment antes de criar (por `flow_step_id` snapshot)
- Dependencies: REQ-007

**REQ-009** [P2]: A operação de re-sync deve ser registrada em `audit_events` com `action = 'flow_resynced'`, contendo o `flow_id`, quantidade de enrollments afetados e steps adicionados/cancelados.
- Dependencies: REQ-007

---

### 5.3 Memória de Conversação da IA

**REQ-010** [P1]: Adicionar campo `ai_memory_messages` (inteiro, default `20`, range `5-100`) em `AccountSettings` (tabela `accounts.settings` JSONB).
- Task hint: atualizar schema Pydantic `AccountSettings` + GET/PUT handlers

**REQ-011** [P1]: O `MessageDispatcher` (agent loop) deve usar `ai_memory_messages` para determinar quantas mensagens do histórico incluir no contexto do LLM.
- Task hint: `message_dispatcher.py` lê `settings.ai_memory_messages`, passa como `limit` para `get_recent_messages`
- Dependencies: REQ-010

**REQ-012** [P2]: A UI de Settings (`/admin/settings`) deve exibir o campo "Memória da IA (últimas N mensagens)" com input numérico (min=5, max=100). O valor deve ser salvo via `PUT /admin/settings`.
- Task hint: componente React + validação frontend
- Dependencies: REQ-010

**REQ-013** [P1]: O campo deve ser carregado via `AccountSettingsRepository` a cada chamada do agent loop (sem cache persistente — lê do DB a cada request para refletir mudanças em tempo real).
- Dependencies: REQ-011

---

### 5.4 Relatórios e Histórico

**REQ-014** [P2]: Novo endpoint `GET /admin/followup/enrollments` com filtros:
- `flow_id` (opcional)
- `contact_phone` (opcional)
- `status` (`active` | `completed` | `cancelled` | todos)
- `page` e `page_size` (paginação, default 20)

Resposta inclui: enrollment_id, contact_phone, customer_name, flow_name, course_name, status, created_at, steps_sent/steps_total.
- Task hint: novo router `followup_enrollments.py` + métodos no `followup_enrollment_repo`
- Dependencies: T1 (índices)

**REQ-015** [P2]: Novo endpoint `GET /admin/followup/enrollments/{enrollment_id}/steps` que retorna todos os `FollowupEnrollmentStep` com: position, template_name ou message_text preview, status, sent_at, scheduled_for.
- Task hint: query em `followup_enrollment_steps` filtrada por enrollment_id
- Dependencies: REQ-014

**REQ-016** [P3]: `GET /admin/followup/flows/{flow_id}` deve retornar estatísticas: `enrollments_active`, `enrollments_completed`, `total_dispatched`.
- Task hint: subquery COUNT agrupado por status em `followup_enrollments`
- Dependencies: T1 (índices)

---

### 5.5 Correções de Integridade e Robustez

**REQ-017** [P0]: `FollowupEnrollmentModel.flow_id` deve ter `ForeignKey('followup_flows.id')` com `ondelete='SET NULL'` (histórico preservado se flow for deletado).
- Task hint: migration `followup_enrollment_fk_and_failure`
- Dependencies: nenhuma (bloqueador base)

**REQ-018** [P0]: `DispatchFollowupStepUseCase` deve tratar falha de envio explicitamente:
- Em caso de exceção no envio: marcar step como `FAILED`, salvar `failure_reason`
- Não propagar exceção — retornar status `'FAILED'`
- Job entra em DLQ automaticamente via worker (comportamento existente mantido)
- Task hint: try/except em `chatnexo.send_template` e `chatnexo.send_message`
- Dependencies: REQ-017 (campo failure_reason precisa existir)

**REQ-019** [P0]: `EnrollContactUseCase` deve usar transação atômica: ou todos os steps são criados e agendados, ou nenhum. Em caso de falha parcial, fazer rollback completo.
- Task hint: envolver criação de steps + agendamento em `session.begin_nested()`
- Dependencies: nenhuma

**REQ-020** [P0]: Adicionar campo `failure_reason` (Text, nullable) em `FollowupEnrollmentStep`.
- Task hint: parte da migration REQ-017; atualizar model + entity
- Dependencies: nenhuma

---

## 6. Technical Architecture

### Architecture Overview

O sistema segue Clean Architecture com 4 camadas:
- **Domain**: entidades, ports (interfaces), value objects — zero dependências externas
- **Application (Use Cases)**: orquestra domain + adapters, sem conhecer HTTP ou DB diretamente  
- **Adapters**: implementações concretas (SQLAlchemy, Redis, ChatNexo, Meta API)
- **Interface**: routers HTTP (FastAPI), worker handlers

Cada use case recebe suas dependências via injeção (ports), permitindo mock em testes sem DB real.

### 6.1 Camadas e Isolamento (SOLID)

```
interface/http/routers/admin/
  followup.py              ← CRUD existente + novos endpoints de relatório
  followup_enrollments.py  ← NOVO: endpoints de relatório de enrollments

shared/application/use_cases/followup/
  enroll_contact.py        ← ATUALIZADO: dedup + transação atômica
  dispatch_followup_step.py ← ATUALIZADO: tratamento de falha explícito
  resync_enrollment.py     ← NOVO: re-sync de flow modificado
  variable_resolver.py     ← sem mudança

shared/adapters/db/repositories/
  followup_enrollment_repo.py ← ATUALIZADO: find_by_flow, list com filtros, bulk ops
  followup_flow_repo.py       ← ATUALIZADO: trigger re-sync on step change

shared/domain/
  entities/followup_enrollment.py ← ATUALIZADO: novo campo failure_reason
  ports/followup_ports.py         ← NOVO: interface IResyncEnrollment

interface/worker/handlers/
  scheduled.py             ← ATUALIZADO: handler 'resync_flow' para processar re-sync async
```

### 6.2 Fluxo de Re-sync

```
Admin edita step →
  PUT /admin/followup/flows/{id}/steps/{step_id}
    → followup_flow_repo.update_step()
      → enfileira job kind='resync_flow' com {flow_id, account_id}
        → worker.handle_resync_flow()
          → ResyncEnrollmentUseCase.execute(flow_id)
            → para cada enrollment ativo:
              → calcula diff (novos steps, cancelados, delay alterado)
              → cria FollowupEnrollmentStep para novos
              → agenda job followup_step para novos
              → cancela job anterior para steps com delay alterado
              → reagenda com novo delay
              → marca CANCELLED steps deletados ainda PENDING
```

### 6.3 Fluxo de Memória de IA

```
Mensagem recebida →
  MessageDispatcher.dispatch()
    → AccountSettingsRepository.get_settings(account_id)
      → memory_window = settings.ai_memory_messages  ← lido do DB
    → ConversationMessageRepository.get_recent(
        account_id=..., phone=..., limit=memory_window
      )
    → monta contexto com últimas N mensagens
    → chama OpenAI com contexto limitado
```

### 6.4 Job Types (Worker)

| kind | Handler | Descrição |
|------|---------|-----------|
| `message` | `handle_message` | (existente) |
| `purchase` | `handle_purchase` | (atualizado: dedup enrollment) |
| `scheduled_welcome` | `handle_scheduled` | (existente) |
| `followup_step` | `handle_scheduled` | (atualizado: failure handling) |
| `resync_flow` | `handle_resync_flow` | **NOVO** |

---

## 7. Data Model Changes

### 7.1 Migration: `followup_enrollment_fk_and_failure` (NOVA)

```sql
-- FR-17: Adiciona FK em followup_enrollments.flow_id
ALTER TABLE followup_enrollments
  ADD CONSTRAINT fk_enrollment_flow
  FOREIGN KEY (flow_id) REFERENCES followup_flows(id) ON DELETE SET NULL;

-- FR-20: Campo failure_reason em enrollment steps
ALTER TABLE followup_enrollment_steps
  ADD COLUMN failure_reason TEXT;

-- Índices para queries de relatório
CREATE INDEX idx_enrollments_flow_status
  ON followup_enrollments(flow_id, status);

CREATE INDEX idx_enrollments_contact_account
  ON followup_enrollments(account_id, contact_id);

CREATE INDEX idx_enrollment_steps_enrollment_status
  ON followup_enrollment_steps(enrollment_id, status);
```

### 7.2 AccountSettings — Campo `ai_memory_messages`

```python
# Em AccountSettings (Pydantic schema / JSONB accounts.settings)
ai_memory_messages: int = Field(default=20, ge=5, le=100)
```

Nenhuma migration necessária — o campo é armazenado no JSONB existente `accounts.settings`.

### 7.3 FollowupEnrollmentStep — Campo `failure_reason`

```python
class FollowupEnrollmentStepModel(Base):
    # ... campos existentes ...
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
```

---

## 8. API Changes

### 8.1 Novos Endpoints

#### `GET /admin/followup/enrollments`
```
Query params:
  flow_id: UUID (opcional)
  contact_phone: str (opcional)
  status: "active" | "completed" | "cancelled" (opcional, default: todos)
  page: int (default: 1)
  page_size: int (default: 20, max: 100)

Response 200:
{
  "items": [
    {
      "id": "uuid",
      "contact_phone": "+5511999999999",
      "customer_name": "João Silva",
      "flow_id": "uuid",
      "flow_name": "Follow-up MVS 7 dias",
      "course_name": "Máquina de Vendas: Shopee",
      "status": "active",
      "created_at": "2026-05-02T03:00:00Z",
      "steps_sent": 2,
      "steps_total": 7
    }
  ],
  "total": 42,
  "page": 1,
  "page_size": 20
}
```

#### `GET /admin/followup/enrollments/{enrollment_id}/steps`
```
Response 200:
[
  {
    "id": "uuid",
    "position": 1,
    "delay_from_purchase_hours": 0,
    "template_name": "mvs_boas_vindas",
    "message_text_preview": null,
    "status": "sent",
    "sent_at": "2026-05-02T03:02:00Z",
    "scheduled_for": "2026-05-02T03:00:00Z",
    "failure_reason": null
  }
]
```

### 8.2 Endpoints Atualizados

#### `GET /admin/followup/flows` (adicionado `stats`)
```json
{
  "id": "uuid",
  "name": "Follow-up MVS 7 dias",
  "course": { "id": "uuid", "name": "Máquina de Vendas: Shopee" },
  "is_active": true,
  "steps_count": 7,
  "stats": {
    "enrollments_active": 143,
    "enrollments_completed": 58
  }
}
```

#### `PUT /admin/settings` — campo `ai_memory_messages`
```json
{
  "openai_api_key": "...",
  "chatnexo_api_key": "...",
  "ai_memory_messages": 20
}
```

---

## 9. Non-Functional Requirements

| Requisito | Valor |
|-----------|-------|
| Latência webhook `subscription.activated` | < 200ms para 202 Accepted |
| Tempo de re-sync por enrollment | < 500ms |
| Re-sync de 1000 enrollments ativos | < 30s (processado em batch assíncrono) |
| Isolamento de falhas | Falha em 1 enrollment de re-sync não cancela os demais |
| Deduplicação | Webhook com mesmo `subscription.id` processado apenas 1x (via `WebhookEvent` dedup existente) |
| Retry de dispatch | Job FAILED vai para DLQ; requeue manual via `/admin/dlq` |
| Observabilidade | Todo enrollment, dispatch e re-sync logado estruturalmente (account_id, flow_id, contact_phone) |

---

## 10. Out of Scope (esta v2)

- Suporte a outros eventos Hubla (`subscription.canceled`, `subscription.refunded`) — estrutura preparada, implementação futura
- Follow-up para outros sistemas além de Hubla (Kiwify, Hotmart) — arquitetura extensível via ports
- A/B testing de flows
- Métricas de abertura/clique de mensagens
- UI de visualização de relatórios (apenas API; frontend pode ser adicionado depois)
- Notificações push para o admin quando enrollment falha
- Follow-up de suporte ao usuário (mencionado pelo operador) — separado, virá em v3

---

## 11. Implementation Plan

### T1 — Migration + Integridade de Dados
- T1.1: Criar migration `followup_enrollment_fk_and_failure` (FK em flow_id, campo failure_reason, índices)
- T1.2: Atualizar `FollowupEnrollmentModel` com FK e `failure_reason`
- T1.3: Atualizar `FollowupEnrollmentStepModel` com `failure_reason`
- T1.4: Atualizar `followup_enrollment_repo.py`: método `find_active_by_flow`, `bulk_create_steps`, `cancel_step`
- T1.5: Testes unitários dos modelos e repo

### T2 — Webhook Hubla v2 (Purchase Handler)
- T2.1: Atualizar `PurchaseHandler` para extrair `purchase_id` de `subscription.id`
- T2.2: Implementar deduplicação de enrollment em `EnrollContactUseCase`
- T2.3: Implementar transação atômica em `EnrollContactUseCase` (todos steps ou rollback)
- T2.4: Suporte a array `event.products` (múltiplos produtos por webhook)
- T2.5: Testes unitários + integration test do fluxo completo
- T2.6: **USER TEST**: Disparar webhook mock → verificar enrollment criado

### T3 — Smart Re-sync de Enrollments
- T3.1: Criar `ResyncEnrollmentUseCase` com lógica de diff (novos, cancelados, delay alterado)
- T3.2: Criar port `IResyncEnrollment` em `domain/ports/`
- T3.3: Adicionar handler `handle_resync_flow` no worker
- T3.4: Registrar job `resync_flow` ao salvar step no `followup_flow_repo`
- T3.5: Implementar cancelamento de job anterior (via scheduled_job_id) no re-sync
- T3.6: Testes unitários do ResyncEnrollmentUseCase (cenários: step novo, step deletado, delay alterado)
- T3.7: **USER TEST**: Criar enrollment → enviar 2 steps → adicionar step → verificar que apenas step novo foi agendado

### T4 — Dispatch Robusto com Error Handling
- T4.1: Atualizar `DispatchFollowupStepUseCase`: capturar exceção de envio → salvar `failure_reason` → retornar `'FAILED'`
- T4.2: Adicionar campo `failure_reason` no retorno do use case
- T4.3: Atualizar worker handler para registrar FAILED sem propagar exceção
- T4.4: Testes unitários: cenário de falha de envio → step marcado FAILED

### T5 — Memória de IA Configurável
- T5.1: Adicionar `ai_memory_messages: int = 20` no schema `AccountSettings` (Pydantic + JSONB)
- T5.2: Atualizar `MessageDispatcher` para ler `ai_memory_messages` do `AccountSettings`
- T5.3: Atualizar `ConversationMessageRepository.get_recent()` para aceitar `limit` dinâmico
- T5.4: Atualizar schema HTTP de settings (GET + PUT) para incluir o campo
- T5.5: Atualizar UI de settings (`/admin/settings`) com input numérico "Memória da IA"
- T5.6: **USER TEST**: Alterar valor no painel → verificar que agent usa N mensagens correto

### T6 — Relatórios e Histórico
- T6.1: Adicionar métodos no `followup_enrollment_repo.py`: `list_with_filters`, `count_steps_by_status`
- T6.2: Criar router `followup_enrollments.py` com GET `/enrollments` e GET `/enrollments/{id}/steps`
- T6.3: Atualizar `GET /followup/flows` para incluir stats (`enrollments_active`, `enrollments_completed`)
- T6.4: Testes dos novos endpoints (integração com DB real)
- T6.5: **USER TEST**: Criar 3 enrollments → listar → verificar paginação e filtros

---

## 12. Testing Strategy

### Unitários (sem DB)
- `ResyncEnrollmentUseCase`: mock repo + job scheduler; testar diff (3 cenários)
- `EnrollContactUseCase`: mock repo; testar dedup e rollback
- `DispatchFollowupStepUseCase`: mock chatnexo; testar falha → failure_reason salvo
- `VariableResolver`: testar todos os sources + edge cases (None values)

### Integração (com DB real + Redis)
- Webhook `subscription.activated` end-to-end: POST → enrollment criado → jobs agendados
- Re-sync após edit de step: step editado → job resync → enrollment atualizado
- Dispatch com template Meta: step PENDING → dispatch → SENT com sent_at

### User Test Checkpoints (validação manual)
1. **T2.6**: Webhook mock → enrollment no DB
2. **T3.7**: Enrollment parcial + flow edit → steps corretos no DB
3. **T5.6**: Settings UI → memory window → agent usa N mensagens
4. **T6.5**: Relatório de enrollments com filtros e paginação

---

## Appendix A — Estrutura de Arquivos Novos

```
apps/api/
├── migrations/versions/
│   └── XXXX_followup_enrollment_fk_and_failure.py   (T1.1)
└── src/
    ├── shared/
    │   ├── application/use_cases/followup/
    │   │   └── resync_enrollment.py                  (T3.1)
    │   ├── domain/ports/
    │   │   └── followup_ports.py                     (T3.2, NOVO ou atualizado)
    │   └── adapters/db/repositories/
    │       └── followup_enrollment_repo.py            (T1.4, T6.1 — atualizado)
    └── interface/
        ├── http/routers/admin/
        │   └── followup_enrollments.py               (T6.2)
        └── worker/handlers/
            └── scheduled.py                          (T3.3 — atualizado)
```

---

## Appendix B — Webhook Payload de Referência

```json
{
  "type": "subscription.activated",
  "version": "2.0.0",
  "event": {
    "product": {
      "id": "QaIlGtff9tlU94JjDKSq",
      "name": "MVS | Máquina de Vendas: Shopee"
    },
    "products": [
      {
        "id": "QaIlGtff9tlU94JjDKSq",
        "name": "MVS | Máquina de Vendas: Shopee",
        "offers": [{ "id": "...", "name": "..." }]
      }
    ],
    "subscription": {
      "id": "9a92f819-490b-4679-976d-820c1eadaf91",
      "payer": {
        "firstName": "Cleide",
        "lastName": "Maria Rodrigues de Barros",
        "document": "01810507812",
        "email": "enfcleidesv@gmail.com",
        "phone": "+5513997160759"
      },
      "activatedAt": "2026-05-02T02:59:25.256Z",
      "paymentMethod": "credit_card",
      "type": "one_time",
      "status": "active"
    },
    "user": {
      "id": "4AaNJsSK8yc7vz92YgAvRsTsbRp1",
      "email": "enfcleidesv@gmail.com",
      "phone": "+5513997160759"
    }
  }
}
```

---

*PRD gerado em 2026-05-21 para o projeto NexoIA / agente-plug. Arquitetura: Clean Architecture + SOLID. Isolamento total entre camadas. Extensível para múltiplos provedores (Hubla, Kiwify, Hotmart) via ports.*
