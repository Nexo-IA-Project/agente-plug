# NexoIA — Índice de Specs e Planos

> Documento de rastreamento de todos os subsistemas do projeto NexoIA.
> Atualizar este arquivo sempre que um spec ou plano for criado/modificado.

## Status

| # | Subsistema | Spec | Plano | Implementação |
|---|-----------|------|-------|---------------|
| ① | **Core** — FastAPI, Redis, Workers, LangGraph, DB, multi-tenancy, idle check | [spec](specs/2026-04-17-nexoia-agent-core-design.md) | [plano](plans/2026-04-17-nexoia-agent-core.md) | ⏳ Pendente |
| ② | **Capability Welcome** — webhook Hubla → boas-vindas WhatsApp | [spec](specs/2026-04-17-nexoia-capability-welcome-design.md) | ⏳ Pendente | ⏳ Pendente |
| ③ | **Capability Access** — aluno sem acesso ao produto | ⏳ Pendente | ⏳ Pendente | ⏳ Pendente |
| ④ | **Capability Refund** — CDC + Guards de reembolso | ⏳ Pendente | ⏳ Pendente | ⏳ Pendente |
| ⑤ | **Capability Loja Express** — follow-up D+1/D+3/D+7 | ⏳ Pendente | ⏳ Pendente | ⏳ Pendente |
| ⑥ | **KB Admin** — painel de gerenciamento de conhecimento | ⏳ Pendente | ⏳ Pendente | ⏳ Pendente |

## Legenda

- ✅ Concluído
- 🔄 Em andamento
- ⏳ Pendente

## Arquivos criados

### Specs (`docs/superpowers/specs/`)

- `2026-04-17-nexoia-agent-core-design.md` — Spec ①: arquitetura base, 9 componentes, 10 tabelas, 12 RFs, 12 RNFs
- `2026-04-17-nexoia-capability-welcome-design.md` — Spec ②: boas-vindas pós-compra, CademiClient stub, AccessCase, D+1

### Planos (`docs/superpowers/plans/`)

- `2026-04-17-nexoia-agent-core.md` — Plano ①: 35 tasks em 12 fases (A–L), TDD completo

## Fonte

PRD original: `PRD_NexoIA_v3.docx` (raiz do repositório)
