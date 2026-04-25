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
| ⑤ | **Capability Loja Express** — follow-up D+0/D+1/D+3/D+5/D+7 | [spec](specs/2026-04-18-nexoia-capability-loja-express-design.md) | [plano](plans/2026-04-18-nexoia-capability-loja-express.md) | ⏳ Pendente |
| ⑥ | **KB Admin** — painel de gerenciamento de conhecimento | [spec](specs/2026-04-18-nexoia-kb-admin-design.md) | [plano](plans/2026-04-18-nexoia-kb-admin.md) | ⏳ Pendente |
| ⑦ | **Capability Knowledge** — RAG com 3 tentativas + sinônimos + keywords | [spec](specs/2026-04-18-nexoia-capability-knowledge-design.md) | [plano](plans/2026-04-18-nexoia-capability-knowledge.md) | ⏳ Pendente |

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

### Planos (`docs/superpowers/plans/`)

- `2026-04-17-nexoia-agent-core.md` — Plano ①: 35 tasks originais + 3 adicionais (Response Composer, Legal History, EscalationReason)
- `2026-04-17-nexoia-capability-welcome.md` — Plano ②: 12 tasks, TDD completo, timing D+1 corrigido (24h)
- `2026-04-18-nexoia-capability-access.md` — Plano ③: 15 tasks, 3092 linhas, TDD completo, cascade + platform scope
- `2026-04-18-nexoia-capability-refund.md` — Plano ④: 22 tasks, 4177 linhas, 5 Guards + Art. 49 + recorrência
- `2026-04-18-nexoia-capability-loja-express.md` — Plano ⑤: 15 tasks, 2748 linhas, D+0→D+7 + scheduler
- `2026-04-18-nexoia-kb-admin.md` — Plano ⑥: 22 tasks, 4087 linhas, pgvector + JWT + RAG
- `2026-04-18-nexoia-capability-knowledge.md` — Plano ⑦: 14 tasks, 2630 linhas, 3 tentativas + ask_context

## Fonte

PRD original: `PRD_NexoIA_v3.docx` e `PRD_G2_EDUCACAO.md` (raiz do repositório)
