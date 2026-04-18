# NexoIA — Índice de Specs e Planos

> Documento de rastreamento de todos os subsistemas do projeto NexoIA.
> Atualizar este arquivo sempre que um spec ou plano for criado/modificado.

## Status

| # | Subsistema | Spec | Plano | Implementação |
|---|-----------|------|-------|---------------|
| ① | **Core** — FastAPI, Redis, Workers, LangGraph, DB, multi-tenancy, idle check | [spec](specs/2026-04-17-nexoia-agent-core-design.md) | [plano](plans/2026-04-17-nexoia-agent-core.md) | ⏳ Pendente |
| ② | **Capability Welcome** — webhook Hubla → boas-vindas WhatsApp | [spec](specs/2026-04-17-nexoia-capability-welcome-design.md) | [plano](plans/2026-04-17-nexoia-capability-welcome.md) | ⏳ Pendente |
| ③ | **Capability Access** — aluno sem acesso ao produto | [spec](specs/2026-04-18-nexoia-capability-access-design.md) | ⏳ Pendente | ⏳ Pendente |
| ④ | **Capability Refund** — CDC + Guards de reembolso | [spec](specs/2026-04-18-nexoia-capability-refund-design.md) | ⏳ Pendente | ⏳ Pendente |
| ⑤ | **Capability Loja Express** — follow-up D+0/D+1/D+3/D+5/D+7 | [spec](specs/2026-04-18-nexoia-capability-loja-express-design.md) | ⏳ Pendente | ⏳ Pendente |
| ⑥ | **KB Admin** — painel de gerenciamento de conhecimento | [spec](specs/2026-04-18-nexoia-kb-admin-design.md) | ⏳ Pendente | ⏳ Pendente |
| ⑦ | **Capability Knowledge** — RAG com 3 tentativas + sinônimos + keywords | [spec](specs/2026-04-18-nexoia-capability-knowledge-design.md) | ⏳ Pendente | ⏳ Pendente |

## Legenda

- ✅ Concluído
- 🔄 Em andamento
- ⏳ Pendente

## Arquivos criados

### Specs (`docs/superpowers/specs/`)

- `2026-04-17-nexoia-agent-core-design.md` — Spec ①: arquitetura base, 9 componentes, 10 tabelas, 12 RFs, 12 RNFs
- `2026-04-17-nexoia-capability-welcome-design.md` — Spec ②: boas-vindas pós-compra, CademiClient stub, AccessCase, D+1
- `2026-04-18-nexoia-capability-access-design.md` — Spec ③: acesso reativo, cascade email→CPF→nome+telefone, REACTIVE_LINK_SENT
- `2026-04-18-nexoia-capability-refund-design.md` — Spec ④: reembolso+retenção, CDC 7 dias, N1/N2, mutex Redis, guards jurídicos
- `2026-04-18-nexoia-capability-loja-express-design.md` — Spec ⑤: follow-up D+0→D+7, LojaExpressCase, stubs formulário+status
- `2026-04-18-nexoia-kb-admin-design.md` — Spec ⑥: upload→chunking→pgvector, JWT multi-tenant, busca RAG, logs de uso
- `2026-04-18-nexoia-capability-knowledge-design.md` — Spec ⑦: RAG capability 3 tentativas + sinônimos + keywords + 4ª com contexto

### Planos (`docs/superpowers/plans/`)

- `2026-04-17-nexoia-agent-core.md` — Plano ①: 35 tasks em 12 fases (A–L), TDD completo
- `2026-04-17-nexoia-capability-welcome.md` — Plano ②: 12 tasks, TDD completo, CademiClient stub

## Fonte

PRD original: `PRD_NexoIA_v3.docx` e `PRD_G2_EDUCACAO.md` (raiz do repositório)
