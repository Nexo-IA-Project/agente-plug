# Integração de IA externa — eventos de negócio, memória e KPIs

**Data:** 2026-05-31  
**Status:** Em design — visão arquitetural aprovada em conversa, aguardando plano de implementação  
**Escopo:** Nexos Flow multi-tenant + integração opcional com IA externa por tenant.

---

## 1. Contexto

O produto nasceu como um sistema específico para um cliente, com IA, automações de pós-compra,
Hubla, ChatNexo/ChatMega e atendimento no WhatsApp no mesmo contexto. A visão mudou: o produto
passa a ser **Nexos Flow**, uma plataforma multi-tenant para automações de onboarding, follow-up e
eventos de negócio vindos de provedores como Hubla, Hotmart, Kiwify, Eduzz, Asaas e outros.

Com isso, a IA específica de um cliente não deve morar no core do Nexos Flow. O core precisa ser
genérico e vendável. Cada cliente pode ter, ou não, uma IA própria com prompt, memória, RAG,
regras, ferramentas, métricas e operação específicas.

Também existe uma separação importante na arquitetura real:

- **ChatNexo/ChatMega:** canal/mensageria WhatsApp.
- **Message Buffer / Nexus Hub:** runtime da conversa em tempo real. Recebe mensagens do canal,
  decide se humano assumiu, chama a IA externa quando aplicável, bloqueia resposta se humano entrou,
  devolve a resposta ao canal e registra mensagens outbound/inbound da conversa.
- **IA externa:** cérebro do atendimento do cliente. Mantém memória conversacional, regras,
  prompt, RAG, decisões e KPIs de IA.
- **Nexos Flow:** plataforma multi-tenant de eventos de negócio, automação, onboarding, disparos,
  integrações e painel.

Decisão central: **Nexos Flow não entra no loop da conversa em tempo real.** Ele não deve virar
roteador entre ChatNexo/ChatMega, Message Buffer e IA. Seu papel é emitir eventos de negócio para
a IA externa e consultar KPIs agregados quando o tenant tiver IA habilitada.

---

## 2. Opinião arquitetural

A ideia é boa e faz sentido comercialmente, mas só é saudável se for tratada como contrato de
integração, não como "um webhook solto de memória".

O desenho recomendado é:

1. **Nexos Flow é fonte de verdade dos eventos que nascem nele**: compra recebida, lead criado,
   onboarding iniciado, intenção de disparar um step, flow completo, falha/resultado recebido do
   runtime de envio, cancelamento/reembolso vindo do provedor, acesso concedido quando o Flow for
   responsável por isso.
2. **Message Buffer é fonte de verdade do estado operacional da conversa em tempo real**: humano
   assumiu, IA pode responder, resposta bloqueada, mensagem inbound/outbound da conversa viva. Ele
   precisa diferenciar `incoming` de `outgoing`; mensagem `outgoing` que veio de fora do runtime da
   IA não pode acionar a IA como se fosse mensagem do cliente.
3. **IA externa é fonte de verdade da memória e dos KPIs de IA**: intenção, resolução, handoff,
   fallback, tokens, custo, latência, uso de ferramentas, classificação e motivos tratados pela IA.
4. **Nexos Flow exibe o painel final**, juntando métricas locais de negócio com métricas agregadas
   vindas da IA externa quando ela estiver habilitada para o tenant.

Não é redundante desde que cada sistema possua uma responsabilidade clara. Seria redundante se o
Nexos Flow tentasse armazenar conversa bruta, controlar handoff humano ou reexecutar lógica do
Message Buffer.

---

## 3. Objetivos

- Permitir que cada tenant configure uma IA externa própria, sem acoplar prompt/regras do cliente ao
  core multi-tenant.
- Enviar para a IA externa os eventos de negócio necessários para ela construir memória contextual.
- Permitir que o painel do Nexos Flow mostre KPIs de IA sem exigir que o usuário abra outro painel.
- Manter o Nexos Flow como fonte de verdade dos eventos de negócio e disparos que ele executa.
- Manter o Message Buffer como runtime da conversa em tempo real.
- Manter a integração opcional: tenants sem IA continuam usando o produto sem ruído.

---

## 4. Não-objetivos

- Não implementar a IA de atendimento do cliente dentro do Nexos Flow.
- Não fazer o Nexos Flow intermediar toda mensagem entre ChatNexo/ChatMega, Message Buffer e IA.
- Não copiar memória completa, conversa bruta ou logs internos da IA para o banco do Nexos Flow.
- Não substituir o Message Buffer.
- Não definir ainda a UI final de KPIs. Esta spec define contrato e fronteiras.
- Não implementar todos os provedores de pagamento agora. O contrato deve nascer preparado para
  múltiplas origens.

---

## 5. Fluxos

### 5.1. Evento de negócio / onboarding

```txt
Hubla/Hotmart/Kiwify/etc.
  -> Nexos Flow recebe webhook
  -> Nexos Flow normaliza evento
  -> Nexos Flow cria/atualiza lead, compra, assinatura, cancelamento etc.
  -> Nexos Flow inicia onboarding/follow-up quando aplicável
  -> Nexos Flow entrega evento de memória/contexto para IA externa se o tenant tiver IA habilitada
  -> Nexos Flow envia mensagem outbound para o Message Buffer
  -> Message Buffer chama ChatNexo/ChatMega para entregar ao cliente
  -> Message Buffer/ChatNexo retorna status de entrega quando existir
  -> Nexos Flow registra status local do step/disparo
```

Exemplo: o Flow envia uma mensagem automática de boas-vindas. A IA externa precisa saber que aquele
contato comprou determinado produto e que uma mensagem de onboarding está sendo enviada. O Nexos
Flow envia um evento versionado para a IA externa, que decide como salvar isso na memória. Em
paralelo, o Flow envia a mensagem como `outgoing` para o Message Buffer, que é quem executa o envio
via ChatNexo/ChatMega.

### 5.2. Conversa em tempo real

```txt
Cliente responde no WhatsApp
  -> ChatNexo/ChatMega recebe mensagem
  -> Message Buffer recebe mensagem
  -> Message Buffer verifica humano/handoff/estado
  -> Message Buffer chama IA externa se aplicável
  -> IA externa usa sua memória e responde
  -> Message Buffer verifica novamente se humano assumiu
  -> Message Buffer devolve resposta ao ChatNexo/ChatMega se permitido
```

O Nexos Flow não participa desse loop. Se ele participasse, haveria integração demais e risco de
duplicar responsabilidades do Message Buffer.

### 5.2.1. Webhook/rota especial para mensagens outgoing externas

Existe um caso separado do incoming normal: o Nexos Flow precisa disparar mensagens automáticas de
onboarding/follow-up, mas o runtime de mensageria continua sendo o Message Buffer. Portanto, o Flow
não deve chamar ChatNexo/ChatMega diretamente nesse desenho; ele deve enviar uma mensagem
`outgoing` para uma rota/contrato do Message Buffer.

Esse tipo de evento **não deve entrar no pipeline de IA como mensagem do cliente**.

Fluxo recomendado:

```txt
Nexos Flow decide disparar uma mensagem de onboarding/follow-up
  -> Nexos Flow envia evento de memória/contexto para IA externa
  -> Nexos Flow envia mensagem outgoing para o Message Buffer
  -> Message Buffer salva/classifica a mensagem como outbound
  -> Message Buffer chama ChatNexo/ChatMega para enviar ao cliente
  -> Message Buffer não chama a IA por causa desse evento
```

Esse webhook/endpoint de outgoing serve para manter o estado conversacional do Message Buffer
coerente. Ele é diferente do contrato de eventos enviado para a IA externa. O contrato com a IA
continua sendo emitido pelo Nexos Flow para memória/contexto.

Campos mínimos desse evento para o Message Buffer:

```json
{
  "direction": "outgoing",
  "origin": "nexos_flow",
  "conversation_id": "123456",
  "phone": "+5511999999999",
  "text": "Parabens pela compra...",
  "sent_at": "2026-05-31T14:20:00Z",
  "metadata": {
    "flow_id": "uuid",
    "step_id": "uuid",
    "provider": "hubla"
  }
}
```

`origin` deve ser explícito. Exemplos: `nexos_flow`, `human`, `ai`, `system`. Isso evita que o
Message Buffer confunda mensagem automática do Flow com resposta humana ou com mensagem inbound do
cliente.

Resposta esperada do Message Buffer para o Nexos Flow:

```json
{
  "accepted": true,
  "message_id": "mb_msg_01J...",
  "conversation_id": "123456",
  "status": "queued"
}
```

O status final de entrega pode chegar depois por callback/evento, porque envio de template e
WhatsApp não deve bloquear o processamento do webhook de pagamento.

### 5.3. Novo disparo do Flow durante uma conversa já existente

```txt
Nexos Flow dispara novo step/follow-up
  -> Nexos Flow entrega evento `onboarding.step.queued` ou `onboarding.step.sent` para IA externa
  -> Message Buffer recebe mensagem outgoing, sem acionar IA
  -> Message Buffer envia pelo ChatNexo/ChatMega
  -> IA externa adiciona esse novo fato à memória do contato
  -> quando o cliente responder, a IA já sabe do novo contexto
```

Esse é o caso principal que justifica a integração: a IA externa precisa conhecer eventos que
aconteceram fora do runtime dela.

### 5.4. KPIs no painel

```txt
Usuário abre dashboard/KPIs no Nexos Flow
  -> Frontend chama backend do Nexos Flow
  -> Backend valida tenant e permissão
  -> Backend consulta métricas locais de negócio
  -> Se IA habilitada: backend consulta API de métricas da IA externa
  -> Backend combina os blocos e devolve para o frontend
```

Tenants sem IA não consultam métricas externas e não exibem blocos dependentes de IA.

---

## 6. Configuração por tenant

Adicionar ao `AccountConfig.integration` ou a tabelas próprias de integração. Existem duas
configurações diferentes:

1. **IA externa:** recebe eventos de memória/contexto e expõe KPIs.
2. **Message Buffer/Nexus Hub:** recebe mensagens outgoing do Flow e executa envio via
   ChatNexo/ChatMega.

### 6.1. IA externa

| Campo | Tipo | Observação |
|---|---|---|
| `external_ai_enabled` | bool | Liga/desliga a integração do tenant. |
| `external_ai_name` | string nullable | Nome exibido no painel. Ex.: "IA de Atendimento". |
| `external_ai_events_url` | url nullable | Endpoint que recebe eventos do Nexos Flow. |
| `external_ai_metrics_url` | url nullable | Base URL/API para KPIs agregados. |
| `external_ai_api_key_encrypted` | string nullable | Credencial criptografada com Fernet, igual demais integrações. |
| `external_ai_tenant_id` | string nullable | ID do tenant no sistema externo, quando diferente do UUID local. |
| `external_ai_mode` | enum | Inicialmente `off`/`events_only`/`metrics`; futuro pode ter `assist`/`autopilot`. |

### 6.2. Message Buffer / runtime de mensageria

| Campo | Tipo | Observação |
|---|---|---|
| `message_buffer_enabled` | bool | Liga/desliga o runtime externo de envio/conversa. |
| `message_buffer_outgoing_url` | url nullable | Endpoint que recebe mensagens outgoing do Flow. |
| `message_buffer_api_key_encrypted` | string nullable | Credencial para o Flow chamar o Message Buffer. |
| `message_buffer_tenant_id` | string nullable | ID do tenant no Message Buffer, se diferente do UUID local. |

Em clientes sem IA, o Message Buffer pode ainda existir como runtime de envio. Em clientes com IA,
ele também controla incoming, handoff e ida/volta da IA.

Na UI de `/settings`, isso deve virar um card próprio:

```txt
/settings
  -> IA externa
       -> status
       -> URL de eventos
       -> URL de métricas
       -> API key/secret
       -> teste de conexão
  -> Message Buffer
       -> URL de outgoing
       -> API key/secret
       -> teste de envio
```

---

## 7. Contrato de eventos

### 7.1. Envelope padrão

Todos os eventos enviados pelo Nexos Flow para IA externa devem ter envelope versionado:

```json
{
  "id": "evt_01J...",
  "version": "2026-05-31",
  "event": "onboarding.step.sent",
  "occurred_at": "2026-05-31T14:20:00Z",
  "tenant": {
    "id": "47418057-77cc-469e-8263-d7311fe64155",
    "external_id": "g2-prod"
  },
  "lead": {
    "id": "uuid",
    "name": "Maria",
    "email": "maria@example.com",
    "phone": "+5511999999999"
  },
  "source": {
    "system": "nexos_flow",
    "provider": "hubla"
  },
  "data": {}
}
```

### 7.2. Eventos iniciais

Eventos que fazem sentido para o primeiro contrato:

| Evento | Quando emitir | Dono/fonte |
|---|---|---|
| `lead.created` | Lead novo criado a partir de um provedor ou entrada manual. | Nexos Flow |
| `lead.updated` | Dados relevantes do lead mudaram. | Nexos Flow |
| `purchase.created` | Compra/assinatura confirmada pelo provedor. | Nexos Flow |
| `purchase.cancelled` | Cancelamento recebido do provedor. | Nexos Flow |
| `refund.created` | Reembolso recebido/processado. | Nexos Flow/provedor |
| `access.granted` | Acesso concedido quando o Flow souber disso. | Nexos Flow |
| `access.failed` | Falha ao conceder/verificar acesso quando o Flow souber disso. | Nexos Flow |
| `onboarding.started` | Lead entrou em um flow. | Nexos Flow |
| `onboarding.step.sent` | Step/follow-up enviado com sucesso. | Nexos Flow |
| `onboarding.step.failed` | Step/follow-up falhou. | Nexos Flow |
| `onboarding.completed` | Todos os steps do enrollment foram enviados. | Nexos Flow |

Eventos de conversa em tempo real, como `message.inbound`, `ai.reply.created` e
`handoff.started`, pertencem ao Message Buffer/IA externa e não são emitidos pelo Nexos Flow,
exceto se futuramente houver uma integração explícita entre esses sistemas para auditoria agregada.

### 7.3. Exemplo de `onboarding.step.sent`

```json
{
  "id": "evt_01JZ_STEP_SENT",
  "version": "2026-05-31",
  "event": "onboarding.step.sent",
  "occurred_at": "2026-05-31T14:20:00Z",
  "tenant": {
    "id": "47418057-77cc-469e-8263-d7311fe64155",
    "external_id": "g2-prod"
  },
  "lead": {
    "id": "2d1d7f8f-0000-4000-9000-000000000001",
    "name": "Maria",
    "email": "maria@example.com",
    "phone": "+5511999999999"
  },
  "source": {
    "system": "nexos_flow",
    "provider": "hubla"
  },
  "data": {
    "flow_id": "uuid",
    "enrollment_id": "uuid",
    "step_id": "uuid",
    "product_name": "Curso X",
    "message": {
      "kind": "template",
      "template_name": "boas_vindas",
      "text_preview": "Parabens pela compra..."
    },
    "chat": {
      "provider": "chatnexo",
      "conversation_id": "123456"
    }
  }
}
```

---

## 8. Entrega, retry e idempotência

Eventos para IA externa não podem depender de request síncrono do usuário nem quebrar o pipeline de
onboarding. O envio deve ser assíncrono e resiliente:

1. Criar uma outbox de eventos externos, ou reaproveitar `job_queue` com persistência suficiente.
2. Persistir evento antes de tentar entregar.
3. Entregar via worker.
4. Assinar request com `Authorization: Bearer <api_key>` ou HMAC.
5. Usar `id` do evento como chave de idempotência.
6. Retentar com backoff.
7. Após limite de tentativas, mandar para DLQ/estado `failed`.
8. Painel de integração deve mostrar saúde básica: último sucesso, último erro, eventos pendentes.

Falha da IA externa não pode impedir envio de mensagem ao aluno.

---

## 9. Contrato de KPIs

O Nexos Flow deve consultar KPIs agregados da IA externa/Message Buffer apenas quando
`external_ai_enabled=true` e quando houver URL/credencial configuradas. Para o usuário final, esses
dados aparecem dentro do painel do Nexos Flow; a origem técnica pode ser a IA, o Message Buffer ou
uma API/fachada mantida pelo ecossistema de IA.

Garantia de fronteira: o Nexos Flow **não lê banco da IA nem banco do Message Buffer diretamente**.
Ele consome uma API agregada e versionada.

### 9.0. Fonte dos KPIs externos

Como o runtime de conversa fica fora do Nexos Flow, os KPIs de IA devem vir de uma API externa.
Essa API pode estar:

- no serviço da IA;
- no Message Buffer/Nexus Hub;
- em uma pequena camada de métricas que consolida IA + Message Buffer.

Do ponto de vista do Nexos Flow, isso deve ser um único contrato:

```txt
Nexos Flow dashboard
  -> /admin/ai/metrics/summary
  -> adapter externo configurado no tenant
  -> API de métricas da IA/runtime
```

O Nexos Flow não precisa saber onde a IA guarda memória, tokens, conversas e decisões. Ele só
precisa receber agregados confiáveis para exibir.

### 9.1. Endpoint sugerido

```txt
GET {external_ai_metrics_url}/summary?from=YYYY-MM-DD&to=YYYY-MM-DD
Authorization: Bearer <api_key>
X-Nexos-Tenant-Id: <account_uuid>
X-External-Tenant-Id: <external_ai_tenant_id>
```

### 9.2. Resposta sugerida

```json
{
  "period": {
    "from": "2026-05-01",
    "to": "2026-05-31"
  },
  "conversation": {
    "total": 320,
    "resolved": 248,
    "handoff": 41,
    "abandoned": 12,
    "avg_response_seconds": 8.4
  },
  "ai": {
    "fallbacks": 9,
    "tokens_used": 1280000,
    "estimated_cost": 18.72,
    "tool_calls": 430
  },
  "intents": [
    { "key": "access", "label": "Acesso", "count": 92 },
    { "key": "refund", "label": "Reembolso", "count": 18 },
    { "key": "cancel", "label": "Cancelamento", "count": 9 }
  ]
}
```

### 9.3. Métricas locais vs externas

O painel deve separar origem dos dados:

- **Nexos Flow local:** leads, compras, cancelamentos de provedor, refunds de provedor, flows,
  steps enviados, falhas de disparo, tempo até onboarding, produto, origem. Exemplo: se a Hubla
  envia cancelamento, o cancelamento é fonte local do Nexos Flow.
- **IA externa:** resolução, handoff, intenção, fallback, custo/tokens, latência de resposta,
  qualidade/score, motivos classificados pela IA.
- **Message Buffer:** estado operacional da conversa em tempo real, bloqueio por humano, origem das
  mensagens, mensagens enviadas pelo runtime e eventos de envio que a IA/atendimento precisem medir.

Quando uma métrica puder existir nos dois lados, definir explicitamente a fonte preferida. Exemplo:
cancelamento vindo da Hubla é fonte local; intenção de cancelamento detectada na conversa é fonte da
IA externa.

---

## 10. IA de suporte do produto

A IA que permanece dentro deste repositório deve ser reposicionada como **IA de suporte ao uso do
Nexos Flow**, não como IA de atendimento do tenant.

Ela pode responder dúvidas sobre:

- configurar integrações;
- entender flows e steps;
- configurar provedores de pagamento;
- resolver dúvidas de permissões;
- explicar status de webhook/disparo;
- orientar uso do painel.

Prompt, nomes e regras específicas de cliente devem ser removidos do core. O prompt deve falar como
suporte do produto Nexos Flow.

---

## 11. Riscos e mitigação

| Risco | Mitigação |
|---|---|
| Webhook de IA virar acoplamento frágil | Envelope versionado, idempotência e DLQ. |
| Duplicar runtime do Message Buffer | Regra explícita: Nexos Flow não entra no loop de conversa. |
| Mensagem outgoing automática acionar IA indevidamente | Rota/contrato de outgoing no Message Buffer com `direction` e `origin`, sem chamada de IA. |
| KPIs inconsistentes entre sistemas | Separar fonte local e externa por métrica. |
| IA externa fora do ar perder contexto | Outbox persistente e retry. |
| Tenants sem IA verem telas quebradas | Integração opcional e cards condicionais. |
| Expor dados sensíveis demais para IA externa | Enviar payload mínimo necessário e permitir mascaramento futuro. |
| Cada IA externa inventar contrato diferente | Publicar contrato único `version=2026-05-31` e evoluir com versionamento. |

---

## 12. Plano de implementação sugerido

### Fase 1 — Contrato e configuração
- Criar campos/tabela de integração de IA externa por tenant.
- Criar página/card em `/settings` para configurar IA externa.
- Criar endpoint de teste de conexão.
- Definir tipos/eventos em código.

### Fase 2 — Outbox de eventos
- Criar `external_ai_events` ou mecanismo equivalente.
- Emitir eventos locais principais: `lead.created`, `purchase.created`,
  `onboarding.started`, `onboarding.step.queued`, `onboarding.step.sent`, `onboarding.step.failed`,
  `onboarding.completed`, `purchase.cancelled`, `refund.created`.
- Definir integração/endpoint de outgoing com Message Buffer para mensagens disparadas pelo Flow.
- Garantir que o Message Buffer envie pelo ChatNexo/ChatMega e não acione IA para esse outgoing.
- Worker entrega com retry e idempotência.
- UI mostra saúde básica da integração.

### Fase 3 — KPIs
- Criar endpoint backend `/admin/ai/metrics/summary`.
- Backend valida permissão e tenant, busca métricas locais e métricas externas.
- Frontend renderiza blocos de IA apenas se habilitada.
- Adicionar fallback visual quando a API externa estiver indisponível.

### Fase 4 — IA de suporte do produto
- Remover nomes/regras específicas de cliente do prompt local.
- Reescrever a IA interna como suporte do Nexos Flow.
- Separar claramente módulos/código de "suporte ao produto" e "integração com IA externa".

---

## 13. Critérios de aceite

- Tenant sem IA continua operando sem chamadas externas e sem telas quebradas.
- Tenant com IA recebe eventos de negócio do Nexos Flow com envelope versionado.
- Falha ao entregar evento para IA não bloqueia onboarding nem disparo WhatsApp.
- Eventos são idempotentes e retentáveis.
- Painel de KPIs distingue métricas locais de métricas externas.
- KPIs de IA aparecem apenas quando a integração estiver habilitada.
- Nexos Flow não intermedeia conversa em tempo real entre ChatNexo/ChatMega, Message Buffer e IA.
- Mensagens outgoing disparadas pelo Nexos Flow são enviadas ao cliente pelo Message Buffer.
- Mensagens outgoing disparadas pelo Nexos Flow não acionam IA no Message Buffer.
- Código/prompt local deixa de mencionar cliente específico e passa a representar o Nexos Flow.
