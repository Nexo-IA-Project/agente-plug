# Integrações como hub de cards (navegação em camadas) — design

**Data:** 2026-05-30
**Status:** Aprovado. Sobre a main (pós #74/#75). Só frontend.

## Context
A página `/settings` (Integrações) mostra tudo solto (ChatNexo + Hubla + Meta empilhados). O dono quer organização por **cards de navegação**: cada integração é um card quadrado (ícone + nome + status); clicar abre a página daquela integração. Pagamentos tem uma camada extra (vários gateways).

## Estrutura de navegação
```
/settings  (Integrações — hub de cards)
  ├─ ChatNexo   → /settings/chatnexo            (Conexão + Atendentes)
  ├─ Pagamentos → /settings/pagamentos          (sub-hub de cards de gateways)
  │     ├─ Hubla (ativo) → /settings/pagamentos/hubla   (config + webhook URL condicional)
  │     └─ Hotmart, Kiwify, Eduzz, Asaas → "em desenvolvimento" (não navega; aviso)
  └─ WhatsApp   → /settings/whatsapp            (credenciais Meta/WhatsApp)
```
Todas as páginas envolvidas por `<RequirePermission perm="settings.view">`. Cada sub-página tem um link "voltar" pro hub anterior. Sidebar segue apontando "Integrações" → `/settings` (hub).

## Componentes
- **`IntegrationCard`** (reutilizável): card quadrado/retangular, ícone destacado (em `bg-*-container`), título, subtítulo curto, badge de status ("Ativo" verde / "Em breve" cinza), efeito hover sutil. Como `<Link>` quando navegável, ou `<button>` que dispara toast "em desenvolvimento" quando não. Grade `grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4`.
- Ícones: ChatNexo `chat`, Pagamentos `payments`, WhatsApp = **SVG inline do WhatsApp** (Material Symbols não tem marca); gateways: ícone genérico + cor de marca (Hubla destaque/ativo; demais acinzentados). Tokens NexoIA, sem hex (cores de marca podem usar `[color:#xxx]` só nos logos se necessário — preferir tokens).

## Páginas
- **`/settings` (hub):** header "Integrações" + grade com 3 cards (ChatNexo, Pagamentos, WhatsApp). Remove o conteúdo inline antigo (ChatNexoSection/IntegrationSection deixam de ser renderizados aqui).
- **`/settings/chatnexo`:** reaproveita `ChatNexoSection` (Conexão + Atendentes). Header "ChatNexo" + voltar.
- **`/settings/whatsapp`:** campos Meta de `IntegrationSection` (meta_api_key, meta_waba_id, meta_app_id, alert_whatsapp_target) via InlineEditField + useFieldSave. Header "WhatsApp" + ícone + voltar.
- **`/settings/pagamentos` (sub-hub):** header "Pagamentos" + voltar pro hub. Grade de cards: **Hubla** (Ativo → navega) + **Hotmart/Kiwify/Eduzz/Asaas** (Em breve → toast "Integração em desenvolvimento").
- **`/settings/pagamentos/hubla`:** config da Hubla (ver abaixo) + voltar pra Pagamentos.

## Página Hubla — webhook URL condicional (comportamento pedido)
- Card "Webhook da Hubla" com:
  - **Campo da chave secreta** (`hubla_webhook_secret`, input secret) **com explicação** clara: "Essa chave autentica os eventos que a Hubla envia ao nosso webhook. Defina uma chave, salve, e cole a URL gerada no painel da Hubla. Sem ela, a Hubla recebe 401."
  - Botões: **Salvar** e **Limpar** (limpar = salva vazio).
  - **Se `hubla_webhook_secret` vazio → o bloco da URL do webhook NÃO aparece.**
  - **Ao salvar uma chave → o bloco da URL aparece com transição suave** (max-height/opacity ~300–350ms ease-in-out), mostrando a URL `/webhook/hubla?token=...` (via `getHublaWebhookToken`) com botão copiar + instruções de configuração (reaproveitar `HublaWebhookCard`, mas renderizado condicionalmente).
  - **Ao limpar (salvar vazio) → o bloco da URL some** (suave). Banco pode salvar vazio.
- Salvar/limpar usa `updateAccountSettings({ hubla_webhook_secret })` (PUT /admin/settings = settings.edit_credentials). Quem não tem a permissão vê em modo leitura (sem salvar) — gate por `can("settings.edit_credentials")`.
- O `HublaWebhookCard` atual deixa de mostrar a mensagem de erro "defina o secret" — agora a URL só aparece quando há chave; refatorar para receber o token/visibilidade do pai ou continuar buscando e o pai controla a revelação.

## Limpeza
- `IntegrationSection` deixa de ser usada em `/settings`. Os campos Meta migram pra `/settings/whatsapp`; Hubla migra pra `/settings/pagamentos/hubla`. Pode-se remover `IntegrationSection` se ninguém mais usa, OU mantê-la decomposta. `ChatNexoSection` reusada em `/settings/chatnexo`.
- `permForPath`/RequirePermission cobrem as novas rotas com `settings.view` (prefixo /settings).

## Testes
- `npx tsc --noEmit` limpo.
- Verificação manual: hub mostra 3 cards; ChatNexo abre conexão+atendentes; Pagamentos abre sub-cards (Hubla ativo, outros "em breve" com toast); Hubla esconde URL sem chave, revela suave ao salvar, some ao limpar; WhatsApp mostra credenciais Meta; voltar funciona; operador sem edit vê read-only.

## Não-objetivos
- Backend (nenhuma mudança). Logos de marca em alta fidelidade (ícones tastefully aproximados bastam).
