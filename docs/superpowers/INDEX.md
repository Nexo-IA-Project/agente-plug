# NexoIA — Índice de Specs e Planos

> Documento de rastreamento de todos os subsistemas do projeto NexoIA.
> Atualizar este arquivo sempre que um spec ou plano for criado/modificado.

## Status

| # | Subsistema | Spec | Plano | Implementação |
|---|-----------|------|-------|---------------|
| ① | **Core** — FastAPI, Redis, Workers, LangGraph, DB, multi-tenancy, idle check | [spec v2](specs/2026-04-24-nexoia-agent-core-v2-design.md) ⚠️ substitui v1 | [plano v2](plans/2026-04-24-nexoia-agent-core-v2.md) (plano v1 obsoleto) | ✅ Concluído |
| ② | **Capability Welcome** — webhook Hubla → boas-vindas WhatsApp | [spec](specs/2026-04-17-nexoia-capability-welcome-design.md) | [plano](plans/2026-04-17-nexoia-capability-welcome.md) | ✅ Concluído |
| ③ | **Capability Access** — aluno sem acesso ao produto | [spec](specs/2026-04-18-nexoia-capability-access-design.md) | [plano](plans/2026-04-18-nexoia-capability-access.md) | ✅ Completo |
| ④ | **Capability Refund** — CDC + Guards de reembolso | [spec](specs/2026-04-18-nexoia-capability-refund-design.md) | [plano v2](plans/2026-04-24-nexoia-capability-refund-v2.md) (plano v1 obsoleto) | ✅ Concluído |
| ⑤ | **Capability Loja Express** — follow-up D+0/D+1/D+3/D+5/D+7 | [spec](specs/2026-04-18-nexoia-capability-loja-express-design.md) | [plano v2](plans/2026-04-25-nexoia-capability-loja-express-v2.md) (plano v1 obsoleto) | ✅ Concluído |
| ⑥ | **KB Admin** — painel de gerenciamento de conhecimento | [spec](specs/2026-04-18-nexoia-kb-admin-design.md) | [plano v2](plans/2026-04-25-nexoia-kb-admin-v2.md) (plano v1 obsoleto) | ✅ Concluído |
| ⑦ | **Capability Knowledge** — RAG com 3 tentativas + sinônimos + keywords | [spec](specs/2026-04-18-nexoia-capability-knowledge-design.md) | [plano v2](plans/2026-04-25-nexoia-capability-knowledge-v2.md) (plano v1 obsoleto) | ✅ Concluído |
| ⑧ | **Account Settings** — página de configuração de credenciais e comportamento via UI | [spec](specs/2026-05-06-nexoia-account-settings-design.md) | [plano](plans/2026-05-06-nexoia-account-settings.md) | ✅ Concluído |
| ⑨ | **Follow-up Engine** — motor de sequências pós-compra dinâmicas (backend + API) | [spec](specs/2026-05-07-nexoia-followup-engine-design.md) | [plano](plans/2026-05-07-nexoia-followup-engine.md) | ⏳ Pendente |
| ⑩ | **Follow-up Flow Manager** — tela de gestão de flows e steps no painel admin | [spec](specs/2026-05-07-nexoia-followup-flow-manager-design.md) | [plano](plans/2026-05-07-nexoia-followup-flow-manager.md) | ⏳ Pendente |
| ⑪ | **Meta Template Manager** — criação e gestão de templates WhatsApp via Meta API | [spec](specs/2026-05-07-nexoia-meta-template-manager-design.md) | [plano](plans/2026-05-07-nexoia-meta-template-manager.md) | ⏳ Pendente |

## Legenda

- ✅ Concluído
- 🔄 Em andamento
- ⏳ Pendente

## Arquivos criados

### Specs (`docs/superpowers/specs/`)

- `2026-04-17-nexoia-agent-core-design.md` — Spec ① v1: arquitetura base (pipeline determinístico) — **OBSOLETO, substituído pela v2**
- `2026-04-24-nexoia-agent-core-v2-design.md` — Spec ① v2: Skill Architecture, Clean Architecture + SOLID, 22 RFs, 13 RNFs
- `2026-04-17-nexoia-capability-welcome-design.md` — Spec ②: boas-vindas pós-compra, CademiClient stub, AccessCase, D+1 (24h)
- `2026-04-18-nexoia-capability-access-design.md` — Spec ③: acesso reativo, cascade email→CPF→nome+telefone, Shopee/KYC, email mismatch
- `2026-04-18-nexoia-capability-refund-design.md` — Spec ④: reembolso+retenção, CDC 7 dias, N1/N2, 5 Guards, mutex Redis 1h
- `2026-04-18-nexoia-capability-loja-express-design.md` — Spec ⑤: follow-up D+0→D+7, LojaExpressCase, stubs formulário+status
- `2026-04-18-nexoia-kb-admin-design.md` — Spec ⑥: upload→chunking→pgvector, JWT multi-tenant, busca RAG, logs de uso
- `2026-04-18-nexoia-capability-knowledge-design.md` — Spec ⑦: RAG capability 3 tentativas + sinônimos + keywords + 4ª com contexto
- `2026-05-07-nexoia-followup-engine-design.md` — Spec ⑨: engine dinâmico pós-compra, 4 tabelas, EnrollContact + DispatchFollowupStep, coexiste com Loja Express
- `2026-05-07-nexoia-followup-flow-manager-design.md` — Spec ⑩: tela admin de flows/steps, drag-and-drop, feature module followup
- `2026-05-07-nexoia-meta-template-manager-design.md` — Spec ⑪: CRUD templates Meta API, editor com preview ao vivo, MetaTemplateClient

### Planos (`docs/superpowers/plans/`)

- `2026-04-17-nexoia-agent-core.md` — Plano ①: 35 tasks originais + 3 adicionais (Response Composer, Legal History, EscalationReason)
- `2026-04-17-nexoia-capability-welcome.md` — Plano ②: 12 tasks, TDD completo, timing D+1 corrigido (24h)
- `2026-04-18-nexoia-capability-access.md` — Plano ③: 15 tasks, 3092 linhas, TDD completo, cascade + platform scope
- `2026-04-18-nexoia-capability-refund.md` — Plano ④: 22 tasks, 4177 linhas, 5 Guards + Art. 49 + recorrência
- `2026-04-18-nexoia-capability-loja-express.md` — Plano ⑤ v1: 15 tasks — **OBSOLETO, substituído pela v2**
- `2026-04-18-nexoia-kb-admin.md` — Plano ⑥ v1: 22 tasks — **OBSOLETO, substituído pela v2**
- `2026-04-18-nexoia-capability-knowledge.md` — Plano ⑦ v1: 14 tasks — **OBSOLETO, substituído pela v2**
- `2026-04-25-nexoia-capability-loja-express-v2.md` — Plano ⑤ v2: 10 tasks, Skill Architecture, worker-driven D+0→D+7
- `2026-04-25-nexoia-kb-admin-v2.md` — Plano ⑥ v2: 12 tasks, FastAPI + JWT + pgvector, sem agent skills
- `2026-04-25-nexoia-capability-knowledge-v2.md` — Plano ⑦ v2: 8 tasks, RAG 4-attempt cascade, Skill Architecture

## Fonte

PRD original: `PRD_NexoIA_v3.docx` e `PRD_G2_EDUCACAO.md` (raiz do repositório)
