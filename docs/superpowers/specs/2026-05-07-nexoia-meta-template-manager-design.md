# NexoIA — Meta Template Manager: Gestão de Templates WhatsApp

**Data:** 2026-05-07  
**Status:** Aprovado  
**Subsistema:** A — Meta Template Manager (backend + frontend)  
**Depende de:** Account Settings (META_API_KEY configurada)

---

## Visão Geral

Implementar a gestão de templates de mensagem WhatsApp Business diretamente no painel NexoIA, sem precisar acessar o Meta Business Manager. O admin cria, visualiza e acompanha o status de aprovação dos templates. A interface replica os campos do editor da Meta: categoria, idioma, cabeçalho (texto/mídia), corpo com variáveis, rodapé e botões.

---

## Requisitos Funcionais

| # | Requisito |
|---|-----------|
| RF-MT01 | Página `/templates` lista todos os templates do WABA com nome, categoria, idioma, status (APPROVED/PENDING/REJECTED) |
| RF-MT02 | Botão "Novo Template" abre página `/templates/new` com formulário completo |
| RF-MT03 | Formulário de criação: nome (snake_case), categoria (MARKETING/UTILITY/AUTHENTICATION), idioma (pt_BR/en_US) |
| RF-MT04 | Cabeçalho opcional: tipo TEXT (com variáveis) ou MEDIA (IMAGE/VIDEO/DOCUMENT — URL ou upload) |
| RF-MT05 | Corpo: textarea com suporte a variáveis `{{1}}`, `{{2}}`... com preview ao vivo |
| RF-MT06 | Rodapé opcional: texto simples |
| RF-MT07 | Botões opcionais: QUICK_REPLY (até 3) ou CALL_TO_ACTION (URL/telefone — até 2) |
| RF-MT08 | Ao salvar, envia para Meta API (`POST /message_templates`) e exibe status retornado |
| RF-MT09 | Lista atualiza status dos templates via `GET /message_templates` (polling manual — botão "Atualizar") |
| RF-MT10 | Templates com status APPROVED ficam disponíveis para seleção nos flows (Spec B) |
| RF-MT11 | Template REJECTED exibe o motivo da rejeição (campo `reason` da Meta API) |
| RF-MT12 | Sidebar exibe item "Templates" com ícone `sms` |

## Requisitos Não-Funcionais

| # | Requisito |
|---|-----------|
| RNF-MT01 | `MetaTemplateClient` segue o padrão `from_account_config()` + `from_settings()` |
| RNF-MT02 | Clean Architecture: port `MetaTemplatePort` em domain, adapter em `shared/adapters/meta/` |
| RNF-MT03 | Credencial `META_API_KEY` + `META_WABA_ID` lidas do `AccountConfig` (editável via Settings) |
| RNF-MT04 | Erros da Meta API (400, 401, nome duplicado) retornam mensagem legível no toast |
| RNF-MT05 | Nenhum template é armazenado em banco próprio — a Meta é a fonte da verdade; apenas `MetaTemplateModel` (já existente em `models.py`) faz cache local para referência nos flows |
| RNF-MT06 | Feature module em `src/features/templates/` seguindo padrão NexoIA |

---

## Arquitetura

### Camada de Domínio

**`shared/domain/ports/meta_template.py`**
```python
class MetaTemplatePort(Protocol):
    async def list_templates(self, waba_id: str) -> list[MetaTemplate]: ...
    async def create_template(self, waba_id: str, payload: CreateTemplatePayload) -> MetaTemplate: ...
```

**`shared/domain/entities/meta_template.py`** (já existe como model, extrair entidade)
```python
@dataclass
class MetaTemplate:
    id: str              # ID retornado pela Meta
    name: str
    category: str        # MARKETING | UTILITY | AUTHENTICATION
    language: str        # pt_BR | en_US
    status: str          # APPROVED | PENDING | REJECTED
    components: list[dict]  # estrutura completa da Meta
    rejection_reason: str | None
```

---

### Camada de Adaptadores

**`shared/adapters/meta/template_client.py`**
```python
class MetaTemplateClient:
    BASE_URL = "https://graph.facebook.com/v19.0"

    @classmethod
    def from_account_config(cls, config: AccountConfig) -> "MetaTemplateClient": ...

    async def list_templates(self, waba_id: str) -> list[MetaTemplate]:
        # GET /{waba_id}/message_templates
        ...

    async def create_template(self, waba_id: str, payload: CreateTemplatePayload) -> MetaTemplate:
        # POST /{waba_id}/message_templates
        ...
```

---

### Admin API

**`interface/http/routers/admin/meta_templates.py`**

```
GET  /admin/meta-templates              → lista templates do WABA (via Meta API)
POST /admin/meta-templates              → cria template (via Meta API)
```

Payload de criação espelha a estrutura da Meta API (components array), validado via Pydantic.

---

### Frontend

**Feature module**
```
apps/web/src/features/templates/
  types.ts                         ← MetaTemplate, CreateTemplateDto, TemplateComponent
  hooks/
    useMetaTemplates.ts             ← GET/POST via admin API
  components/
    TemplateList.tsx                ← lista com status colorido
    TemplateStatusBadge.tsx         ← APPROVED=verde, PENDING=amarelo, REJECTED=vermelho
    TemplateForm.tsx                ← formulário completo de criação
    TemplateComponentEditor.tsx     ← editor de componentes (header/body/footer/buttons)
    VariableHighlighter.tsx         ← destaca {{1}}, {{2}} no preview
    TemplatePreview.tsx             ← preview ao vivo do template no formato WhatsApp
```

**Páginas**
```
apps/web/src/app/(admin)/templates/
  page.tsx                          ← lista de templates
  new/
    page.tsx                        ← formulário de criação
```

**Wireframe conceitual — Lista**
```
┌─────────────────────────────────────────────────────┐
│ Templates WhatsApp              [↺ Atualizar] [+ Novo]│
│─────────────────────────────────────────────────────│
│ mv_boas_vindas    MARKETING  pt_BR  ● APPROVED       │
│ mv_link_aula      MARKETING  pt_BR  ● APPROVED       │
│ mv_pesquisa_10    UTILITY    pt_BR  ○ PENDING        │
│ mv_pesquisa_30    UTILITY    pt_BR  ✕ REJECTED       │
│                                    Motivo: conteúdo  │
└─────────────────────────────────────────────────────┘
```

**Wireframe conceitual — Formulário de criação**
```
┌─────────────────────────────────────────────────────┐
│ Novo Template                                        │
│─────────────────────────────────────────────────────│
│ Nome*         [mv_nome_do_template              ]    │
│ Categoria*    [MARKETING ▾]   Idioma* [pt_BR ▾]     │
│                                                      │
│ Cabeçalho     [Nenhum ▾]  (TEXT / IMAGE / VIDEO)    │
│                                                      │
│ Corpo*                                               │
│ ┌──────────────────────────────────────────────┐   │
│ │ Olá {{1}}, seu acesso está disponível!       │   │
│ └──────────────────────────────────────────────┘   │
│ [+ Adicionar variável]                              │
│                                                      │
│ Preview WhatsApp:                                    │
│ ┌─────────────────────────┐                         │
│ │ Olá João, seu acesso... │                         │
│ └─────────────────────────┘                         │
│                                                      │
│ Rodapé        [                                 ]   │
│                                                      │
│ Botões        [+ Adicionar botão]                   │
│                                                      │
│                          [Cancelar] [Enviar para Meta]│
└─────────────────────────────────────────────────────┘
```

---

## Variáveis de Ambiente Necessárias

```
META_API_KEY=       # token de acesso da Meta (Graph API)
META_WABA_ID=       # ID do WhatsApp Business Account
```

Ambas já configuráveis via página de Settings (Spec Account Settings).

---

## Arquivos

### Novos
```
apps/api/src/shared/domain/ports/meta_template.py
apps/api/src/shared/adapters/meta/template_client.py
apps/api/src/interface/http/routers/admin/meta_templates.py
apps/api/src/interface/http/schemas/meta_templates.py
apps/api/tests/unit/interface/admin/test_meta_templates_router.py

apps/web/src/features/templates/types.ts
apps/web/src/features/templates/hooks/useMetaTemplates.ts
apps/web/src/features/templates/components/TemplateList.tsx
apps/web/src/features/templates/components/TemplateStatusBadge.tsx
apps/web/src/features/templates/components/TemplateForm.tsx
apps/web/src/features/templates/components/TemplateComponentEditor.tsx
apps/web/src/features/templates/components/VariableHighlighter.tsx
apps/web/src/features/templates/components/TemplatePreview.tsx
apps/web/src/app/(admin)/templates/page.tsx
apps/web/src/app/(admin)/templates/new/page.tsx
```

### Modificados
```
apps/api/src/shared/config/settings.py              + META_WABA_ID
apps/api/src/main.py                                + router meta_templates
apps/web/src/shared/components/layout/Sidebar.tsx   + item "Templates" (sms)
apps/web/src/lib/api.ts                             + funções de templates API
```

---

## Fora de Escopo

- Edição de template após criação (Meta não permite — só deletar e recriar)
- Deleção de templates via painel → v2
- Upload de mídia direto para o Meta → v1 usa URL externa
- Localização em múltiplos idiomas por template → v2
