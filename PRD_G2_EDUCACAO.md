# NexoIA — Plataforma de Suporte Inteligente

## PRD Completo — Fase 1

**Versão 3.0 — Clean Architecture · SOLID · Modular · Escalável**  
**Abril 2026 | G2 Educação × NexoIA**

---

## 1. Visão do Produto

Construir a primeira versão operacional da IA de suporte da NexoIA: multi-tenant, integrada ao painel operacional ChatNexo, com arquitetura Python seguindo Clean Architecture e princípios SOLID, usando LangGraph como orquestrador de fluxos stateful.

A solução é composta por quatro camadas independentes:

- Painel operacional ChatNexo (Node.js existente) — inbox, CRM, canal WhatsApp
- Backend IA (Python) — engine, regras de negócio, memória, capabilities
- Painel KB Admin — interface para alimentar a base de conhecimento sem editar prompts
- Infraestrutura de dados — repositório separado: PostgreSQL + Redis rodando em Docker

---

## 2. Contexto e Problema de Negócio

| Dimensão | Dado |
|---|---|
| Volume fora do horário | 47% das mensagens chegam sem resposta útil |
| Score médio humano | 4.30/10 — resolução 2.37/10 (piorando) |
| Reembolsos (fev/2026) | R$ 750.000 — ~14-15% do faturamento mensal |
| Principal gatilho | Medo de golpe por falta de resposta rápida após compra |
| Top volume | Acesso — problema simples, altíssimo volume |
| Loja Express | Sem acompanhamento proativo → vira reembolso |
| Sofia atual | Funciona, mas regras no prompt, alto acoplamento, ajuste manual |

---

## 3. Fluxo Proativo Pós-Compra — Webhook de Compra

Este é o fluxo mais crítico para redução de reembolso. O aluno compra, demora a receber acesso ou fica inseguro, e pede reembolso em minutos por medo de golpe. A IA precisa agir antes que o aluno mande mensagem.

**Regra:** confirmado nos documentos: o Excalidraw descreve “Compra recente com medo de golpe vira prioridade” e “Resposta Imediata — Não deixa o aluno sem resposta”. O kickoff descreve o caso real: aluno compra às 2h21 e pede reembolso às 2h35. A Sofia atual tem `proactive-outreach.js` em produção.

### 3.1 Trigger — Webhook de Nova Compra

Quando uma compra é confirmada na plataforma de pagamentos (Hubla), um webhook é disparado para o backend IA com os dados da compra.

| Atributo | Descrição |
|---|---|
| Origem do evento | Hubla (plataforma de pagamentos) via webhook POST |
| Dados recebidos | nome, email, telefone, produto comprado, valor, data/hora |
| Autenticação | Token secreto no header — validado pelo backend antes de processar |
| Idempotência | Redis NX por `purchase_id` — evita disparo duplo para a mesma compra |
| SLA | Mensagem de boas-vindas enviada em até 60 segundos após o webhook |

### 3.2 Fluxo de Boas-Vindas (Mensagem Proativa)

1. Hubla dispara webhook `POST /api/webhooks/purchase` para o backend IA
2. Backend valida token, verifica idempotência (Redis NX), registra o evento
3. Identifica o número de WhatsApp do aluno (via telefone do webhook ou busca na Cademi)
4. Verifica se já existe conversa ativa com este contato no ChatNexo
5. Envia mensagem de boas-vindas via ChatNexo → Meta API usando template aprovado
6. Inclui no template: nome do aluno, nome do produto, link nominal de auto-login
7. Aguarda resposta. Se o aluno responder, a conversa entra no fluxo reativo normal
8. Se o aluno não responder em 1 hora: agenda follow-up D+1 via template

**Crítico:** a mensagem de boas-vindas deve usar template aprovado pela Meta — é uma mensagem proativa (fora da janela de 24h). Nunca enviar texto livre como primeiro contato.

**Info:** se o aluno responder à mensagem de boas-vindas, a janela de 24h se abre e a IA pode responder livremente a partir desse ponto.

### 3.3 Templates Meta Necessários

| Template ID | Uso e conteúdo |
|---|---|
| `welcome_purchase` | Boas-vindas pós-compra com nome, produto e link de acesso. Enviado em até 60s após webhook |
| `access_reminder_d1` | Lembrete de acesso se o aluno não entrou no D+1 após a compra |
| `loja_express_d1` | Follow-up Loja Express — verifica se formulário foi respondido |
| `loja_express_d3` | Check de progresso da loja — informa status |
| `loja_express_d7` | Alerta do prazo crítico — 7 dias, resolve ou escala |
| `reengagement` | Reativação de contatos inativos (sem resposta há mais de X dias) |

### 3.4 Fluxo Reativo — Aluno que Manda Mensagem

Quando o aluno manda mensagem primeiro (sem webhook prévio, ou após a boas-vindas):

9. ChatNexo recebe mensagem via webhook do WhatsApp Business API
10. Media Processing: áudio → Whisper, vídeo/imagem/PDF → texto, antes de chegar ao agente
11. Payload enriquecido enviado ao backend IA (texto, metadados, contato, canal)
12. Fila de mensagens prioriza por intent detectado: URGENTE → ALTA → NORMAL → BAIXA
13. Backend carrega checkpoint da thread + memória longa do contato
14. Intent Router classifica, seleciona playbook e executa capability
15. Resposta retorna ao ChatNexo → entregue ao aluno via Meta API

---

## 4. Diretriz Estratégica

**Regra:** resolver o máximo possível com IA. Humano entra apenas para exceções que a IA não consegue tratar.

**Atenção:** a prioridade máxima é velocidade de primeira resposta — especialmente nos primeiros 60 minutos após a compra.

---

## 5. Arquitetura — Clean Architecture + SOLID

### 5.1 Princípios Arquiteturais

| Princípio | Aplicação |
|---|---|
| Clean Architecture | Separação em camadas: Domain → Application → Infrastructure → Interface. Regras de negócio no núcleo, sem dependência de framework |
| SOLID | Single Responsibility por módulo/capability; Open/Closed para adicionar capabilities; Dependency Injection em todas as integrações |
| Modularidade | Cada capability é um módulo independente. Adicionar nova capability não toca o core |
| Escalabilidade | Novos tenants sem reescrita. Workers escaláveis horizontalmente. Fila com prioridade |
| Banco separado | PostgreSQL e Redis em repositório próprio, rodando via Docker Compose. O backend consome via connection string — sem dependência de onde o banco está |
| Regras fora do prompt | O LLM executa comportamento. Regras de negócio são código Python testável — nunca instrução no prompt |

### 5.2 Estrutura de Camadas

| Camada | Responsabilidade |
|---|---|
| Domain (núcleo) | Entidades, regras de negócio, playbooks, guards, árvores de decisão. Zero dependência externa |
| Application | Use cases por capability (`AccessUseCase`, `RefundUseCase`, etc.). Orquestra domain + infra |
| Infrastructure | Adapters: Hubla (Playwright), Cademi (REST), ChatNexo (webhook/API), pgvector, Redis |
| Interface | FastAPI routes: `/webhook/purchase`, `/webhook/message`, `/api/kb-admin`, `/health` |

### 5.3 Repositórios

| Repositório | Conteúdo |
|---|---|
| `nexoia-agent` | Backend IA em Python. Clean Architecture, LangGraph, capabilities, regras, RAG |
| `nexoia-infra` | Repositório separado: `docker-compose.yml` com PostgreSQL + pgvector + Redis. Migrations Alembic |
| `nexoia-panel` | ChatNexo — painel Node.js existente. KB Admin Panel embutido neste repositório |

**Atenção:** o banco de dados (PostgreSQL + Redis) roda em Docker, em repositório separado (`nexoia-infra`). O backend conecta via `DATABASE_URL` e `REDIS_URL`. Nunca acoplar migrations ao repositório do agente.

### 5.4 Infraestrutura de Dados (`nexoia-infra`)

Repositório independente com `docker-compose.yml` e scripts de inicialização:

- PostgreSQL 15 + extensão `pgvector` — dados operacionais, embeddings, memória longa
- Redis 7 — sessão, deduplicação (NX), mutex de reembolso, state do circuit breaker, fila
- Migrations via Alembic (executado pelo backend no startup, não pelo repositório de infra)
- Volumes persistentes nomeados para não perder dados entre restarts
- Health checks configurados para PostgreSQL e Redis
- Variáveis de ambiente via `.env` — nunca hardcoded

### 5.5 Fluxo Completo de Mensagem

16. Meta API → ChatNexo: evento de mensagem recebida  
17. ChatNexo: Media Processing (áudio→texto via Whisper, imagem→texto via Vision, PDF→texto)  
18. ChatNexo: monta payload enriquecido (texto, metadados, contato, canal, turno)  
19. ChatNexo: `POST /webhook/message` → backend IA  
20. Backend: valida token, dedup Redis NX por `messageId` (5min TTL)  
21. Backend: enfileira job com prioridade (URGENTE=1 / ALTA=2 / NORMAL=3 / BAIXA=4)  
22. Worker: carrega checkpoint LangGraph da thread  
23. Worker: Context Builder lê memória curta + memória longa + diferencia humano vs IA  
24. Worker: Intent Router classifica intenção (6 categorias) + sentimento (5 categorias)  
25. Worker: seleciona playbook e executa Capability  
26. Capability: executa regras de domínio, chama tools (Hubla/Cademi/KB)  
27. Response Composer: monta resposta, tags, status, ação  
28. Checkpoint salvo; fatos úteis persistidos na memória longa  
29. Backend: `POST` ChatNexo Action API com resposta + comandos  
30. ChatNexo: envia mensagem via Meta API para o WhatsApp do aluno

---

## 6. Painel de Administração de Conhecimento (KB Admin)

Interface web embutida no ChatNexo para que a equipe alimente a KB da IA sem editar prompts ou código.

| Funcionalidade | Descrição |
|---|---|
| Login / autenticação | E-mail + senha com JWT. Perfis: admin, editor, viewer. Multi-tenant |
| Upload de documentos | PDF, DOCX, TXT, MD, imagens (OCR). Drag-and-drop ou upload em lote |
| Organização | Pastas e tags por categoria e tenant: acesso, reembolso, shopee, loja, etc. |
| Visualização de chunks | Mostra como o documento foi fragmentado e indexado |
| Status de indexação | Pendente / Processando / Indexado / Erro — com contagem de chunks |
| Busca de teste | Campo para simular uma query e ver quais chunks a IA retornaria |
| Exclusão / atualização | Remover ou substituir documentos. Re-indexação automática |
| Logs de uso | Quais documentos foram consultados, frequência, queries sem resultado |

**Atenção:** o painel KB Admin não expõe prompts. O operador alimenta conhecimento — as regras são código, não prompt.

---

## 7. Capabilities da Fase 1

### 7.1 Proactive Welcome Capability — Boas-vindas Pós-Compra

Disparada pelo webhook de nova compra. Não espera o aluno mandar mensagem.

31. Recebe evento de compra (webhook Hubla): nome, email, telefone, produto  
32. Verifica idempotência: Redis NX por `purchase_id`  
33. Busca dados completos do aluno na Cademi: link nominal de auto-login  
34. Envia template de boas-vindas via ChatNexo com nome + produto + link  
35. Registra `AccessCase` com status `link_enviado_proativo`  
36. Se aluno não responder em 1h: agenda template `access_reminder_d1`

**Regra:** SLA de 60 segundos entre webhook e mensagem entregue. Exceção: falha de integração com Cademi.

### 7.2 Access Capability — Recuperação de Acesso

Fluxo reativo. Aluno manda mensagem reclamando de acesso.

37. Busca aluno por e-mail na Cademi  
38. Se encontrado: gera link nominal e envia  
39. Confirma que o aluno conseguiu entrar  
40. Se e-mail não encontrado: pede CPF → busca por CPF → informa e-mail associado  
41. Se CPF não encontrado: tenta por nome + telefone  
42. Após 3 tentativas sem resultado: escala silenciosamente

**Regra:** link de acesso deve ser nominal (auto-login) — aluno não cria senha.

**Atenção:** se e-mail de compra diferir do e-mail informado: oferecer atualizar cadastro antes de reenviar.

**Crítico:** nunca usar `resend_access` para problemas de cadastro Shopee ou KYC — são plataformas distintas.

### 7.3 Refund & Retention Capability

#### Passo 1 — Coleta

**Crítico:** sempre perguntar o motivo antes de pedir e-mail. Nunca ir direto para “me passa o e-mail”.

43. Aluno não disse o motivo: “Me conta o que aconteceu?”  
44. Aluno já disse: 1 frase de empatia curta  
45. Pedir e-mail + CPF na mesma mensagem  
46. Buscar compra na Hubla assim que tiver o e-mail

#### Passo 2 — Prazo

| Situação | Ação |
|---|---|
| ≤ 7 dias da compra | Dentro do prazo → Passo 3 (Retenção) |
| ≥ 7 dias da compra | Fora do prazo → Passo 5 (Deny) |
| Recorrente (`isRecurring=true`) | Prazo conta da primeira parcela |
| Compras separadas | Cada compra tem prazo independente |

**Crítico:** nunca falar sobre prazo sem ter buscado a compra na Hubla antes.

#### Passo 3 — Retenção (dentro do prazo)

**Crítico:** N1 obrigatório antes de qualquer reembolso, salvo exceções.  
**Crítico:** se N1 recusado, N2 obrigatório. Proibido ir direto ao reembolso após N1 recusado.

- Exceção — compra duplicada: reembolsa sem retenção
- Exceção — aluno CMP insistente: argumentação especial sem N1/N2
- N1 (Acesso Vitalício): transforma acesso em permanente. Aceite → entrega e encerra
- N2 (Mentoria de Tráfego): curso de tráfego pago liberado grátis. Aceite → entrega e encerra
- Máximo 2 ofertas. Nunca repetir a mesma oferta. Recusa dupla → Passo 4

#### Passo 4 — Processar reembolso

**Crítico:** nunca dizer “fizemos” ou “processado” — é assíncrono. Usar apenas a mensagem padrão.  
**Crítico:** nunca chamar `finish_attendance` no mesmo turno que `process_refund`.

Mensagem padrão:

> Tô processando seu reembolso agora! O prazo de estorno de pix é até 72 horas e cartão de 1 a 2 faturas, ambos dependem da sua operadora. Você vai receber a confirmação assim que o processamento terminar, tá?

#### Passo 5 — Deny (fora do prazo)

**Crítico:** fora do prazo = zero retenção. Informar e negar.

- Informar data da compra e que passou dos 7 dias
- Na 3ª insistência: escala silenciosa
- Se mencionar Procon/advogado/ação judicial: escala silenciosa imediata — nenhuma mensagem
- Art. 49 CDC: se aluno pediu dentro do prazo em qualquer canal anterior → processar reembolso

#### Guards de Segurança

| Guard | Descrição |
|---|---|
| Guard 1 — Pedido explícito | Bloqueia reembolso se aluno não pediu explicitamente neste turno |
| Guard 2 — Produto bloqueado | “Não quero cancelar X” → bloqueia esse produto na conversa |
| Guard 3 — Retenção obrigatória | Bloqueia `process_refund` se N2 não foi oferecido após N1 recusado |
| Guard 4 — Same-turn block | Nunca `finish_attendance` no mesmo turno que `process_refund` |
| Guard 5 — Mutex Redis | `SET NX` por produto+contato (TTL 1h) — impede jobs duplicados |

### 7.4 Knowledge Capability — Dúvidas Técnicas

47. Tentativa 1: palavras exatas do aluno (threshold 0.55)  
48. Tentativa 2: expansão de sinônimos (160+ termos mapeados)  
49. Tentativa 3: extração de keywords (remove stopwords)  
50. Pedir contexto objetivo ao aluno → 4ª busca direcionada  
51. Persistir sem resultado: escala silenciosa

**Atenção:** quando dúvida vier genérica, pedir contexto objetivo antes de buscar.

### 7.5 Loja Express Capability

| Momento | Ação da IA |
|---|---|
| D+0 (compra) | Confirmar recebimento, enviar passo a passo do formulário |
| D+1 (follow-up) | Verificar formulário. Se não respondido: reenviar lembrete via template |
| D+3 (check) | Verificar status da loja, informar progresso ao aluno |
| D+5 (alerta) | Se loja não entregue: verificar bloqueio, acionar operação |
| D+7 (prazo crítico) | Último dia do prazo de reembolso. Resolver ou escalar com urgência |

**Crítico:** follow-ups D+1 a D+7 usam templates Meta — são mensagens proativas fora da janela de 24h.

### 7.6 Escalation Capability

| Situação | Ação |
|---|---|
| Aluno pediu humano 3x | Escala na 3ª insistência |
| Chargeback / contestação | Escala imediata |
| Bug após 3 tentativas | Escala com descrição |
| PDF / material de live | Escala silenciosa |
| Loja Express — problema operacional | Escala silenciosa para operação |
| Compra não encontrada (3 buscas) | Escala silenciosa |
| Procon / advogado / ação judicial | Escala silenciosa imediata. Nenhuma mensagem ao aluno |
| 3ª insistência pós-deny | Escala silenciosa |

**Crítico:** sempre silencioso. Nunca dizer “vou te transferir”. Nunca escalar por erro de API — usar retry.

---

## 8. Regras de Comunicação da IA

| Atributo | Regra |
|---|---|
| Identidade | Especialista de Sucesso do Aluno. Pessoa real do time. Nunca se revela como IA |
| Tom | Calorosa, direta, competente. “Amiga próxima que trabalha na empresa.” |
| Linguagem | Informal: “vc”, “tb”, “pra”, “tá”, “né”, “beleza” |
| Mensagens | Máximo 300 caracteres, 2-4 linhas |
| Proibido | “putz”, “puts”, “poxa”, “que chato”, “Claro!”, “entendo” repetido |
| Formato | Nunca bullets, negrito, itálico ou cabeçalhos no WhatsApp |

| Sentimento | Comportamento |
|---|---|
| Neutro/Positivo | Tom amigável, emoji ok |
| Frustrado | 1 frase de empatia → ação direta |
| Irritado | Sério, direto, sem emoji. Ação imediata |
| Ansioso | “Fica tranquilo(a), vou cuidar disso” |
| Hostil | Profissional e calmo. 1 tentativa → escala |

---

## 9. Modelo de Memória

| Tipo | Descrição |
|---|---|
| Curto prazo (thread) | Checkpoint LangGraph por conversa. Estado do fluxo, tentativas, handoff |
| Longo prazo (contato) | Fatos: e-mail, produtos, histórico de retenção, personalidade, preferências |
| Diferenciação humano×IA | Context Builder deve separar mensagens de operadores vs respostas da IA |
| Histórico jurídico | Busca em todas as conversas anteriores para Art. 49 CDC |

---

## 10. Requisitos Funcionais

| ID | Requisito | Descrição |
|---|---|---|
| RF-01 | Webhook de compra | Receber evento de nova compra (Hubla) com validação de token e idempotência Redis |
| RF-02 | Mensagem proativa | Enviar template de boas-vindas em ≤60s após webhook, com link nominal |
| RF-03 | Webhook de mensagem | Receber payload enriquecido do ChatNexo (texto transcrito, metadados, contato) |
| RF-04 | Fila com prioridade | URGENTE (reembolso) > ALTA (acesso) > NORMAL > BAIXA por intent detectado |
| RF-05 | Contexto conversacional | Memória curta (checkpoint) + longa (fatos) a cada turno |
| RF-06 | Diferenciação humano×IA | Context Builder identifica e separa mensagens de operadores no histórico |
| RF-07 | Classificação de intenção | 6+ categorias de intent; 5 categorias de sentimento; seleção de playbook |
| RF-08 | Access Capability | Busca escalonada + link nominal + update email + fallback 3 tentativas |
| RF-09 | Refund & Retention | N1/N2 + guards + prazo + deny + Art.49 + garantia condicional + multi-produto |
| RF-10 | Knowledge Capability | RAG 3 tentativas + sinônimos + threshold 0.55 + reformulação |
| RF-11 | Loja Express | Jornada 7 dias + follow-up via templates + agente especialista |
| RF-12 | Escalation | Handoff silencioso com triggers definidos. Nunca por erro de API |
| RF-13 | Persistência | Memória, checkpoints, casos (Refund, Access, LojaExpress, Retention) |
| RF-14 | Integração Hubla | Browser automation. Workers assíncronos, mutex, callback ao aluno |
| RF-15 | Integração Cademi | Busca, link nominal, update email, matrícula em produtos de retenção |
| RF-16 | Deduplicação | 3 camadas: `messageId` NX, content hash, job idempotency |
| RF-17 | Templates Meta | Envio proativo fora da janela de 24h via templates aprovados |
| RF-18 | KB Admin — upload | Interface para upload, chunking, indexação pgvector, busca de teste |
| RF-19 | KB Admin — auth | Login JWT multi-tenant. Perfis: admin, editor, viewer |
| RF-20 | Circuit breaker | Detectar loops, repetições, frustração e acionar escalação automaticamente |

---

## 11. Requisitos Não Funcionais

| ID | Requisito | Descrição |
|---|---|---|
| RNF-01 | Escalabilidade | Novos tenants sem reescrita. Workers escaláveis. Nova capability sem tocar o core |
| RNF-02 | Clean Architecture | Domain → Application → Infrastructure → Interface. Zero dependência de framework no domínio |
| RNF-03 | SOLID | SRP por módulo. OCP para capabilities. DI em todas as integrações |
| RNF-04 | Banco separado | PostgreSQL + Redis em repositório Docker independente do agente |
| RNF-05 | Deduplicação | 3 camadas. Falha em qualquer camada não causa duplicata |
| RNF-06 | Latência | < 60s primeira resposta pós-compra. < 30s resposta reativa |
| RNF-07 | Confiabilidade | Retry exponencial. Timeout por operação. Fail-closed em dúvida |
| RNF-08 | Compliance Meta | Nunca mensagem livre fora da janela de 24h. Sempre template aprovado |
| RNF-09 | Testabilidade | Testável por camada, use case e capability. Mocks para Hubla e Cademi |
| RNF-10 | Observabilidade | Logs estruturados com `correlationId`. Rastreamento de intent e capability |
| RNF-11 | Segurança | Isolamento por tenant. Segredos via env. Tokens de webhook validados |
| RNF-12 | Evolução | Arquitetura pronta para analytics, shadow mode e aprendizado em fases futuras |

---

## 12. Integrações da Fase 1

| Sistema | Responsabilidade | Método |
|---|---|---|
| ChatNexo | Canal entrada/saída. Payload enriquecido, Media Processing, Action API (resposta, transfer, tags) | Webhook + REST |
| Meta Official API | WhatsApp do cliente — via ChatNexo. Templates para proativas fora da janela de 24h | Via ChatNexo |
| Hubla (compras) | Webhook de nova compra + busca de compra + reembolso + deny. Sem API REST → browser automation | Playwright |
| Cademi (membros) | Busca de aluno, link nominal, reenvio, update email, matrícula em produtos de retenção | REST |
| Loja Express | Status, formulário, fornecedor, planilha operacional | A definir por tenant |
| PostgreSQL + pgvector | Dados operacionais, embeddings KB, memória longa. Repositório `nexoia-infra` | Docker |
| Redis | Dedup NX, mutex reembolso, circuit breaker, fila de mensagens, session cache | Docker |

**Crítico:** a Hubla não tem API REST pública. Toda operação é via browser automation (Playwright). Timeout 150s, concorrência=1, self-healing de sessão, MFA via IMAP Gmail.

---

## 13. Modelo de Dados — Entidades Principais

| Entidade | Descrição |
|---|---|
| Tenant | Configurações, credenciais, KB, políticas por cliente |
| Contact | Aluno: `phone`, `name`, `email`, `tenant_id`, `tags` |
| Conversation | Thread: `contact_id`, `status`, `intent`, `escalation_reason` |
| Message | `role` (`user`/`assistant`/`human_agent`), `content`, `intent`, `media_type` |
| ConversationCheckpoint | Estado LangGraph por thread |
| ContactMemoryFact | Memória longa: tipo, valor, confiança |
| PurchaseWebhookEvent | Evento de compra recebido: `purchase_id`, produto, aluno, status |
| RefundCase | Produto, email, prazo, retenção aplicada, `deadline_corrected` |
| RetentionCase | Nível N1/N2, oferta, resultado |
| AccessCase | Email buscado, método, link enviado, compra proativa |
| LojaExpressCase | Status, formulário, checkpoints D+1 a D+7 |
| CapabilityExecution | Log: capability, tools, duração, resultado |
| KnowledgeChunk | Fragmento: `document_id`, texto, embedding (`pgvector`) |
| IntegrationConfig | Credenciais por tenant |
| MetaTemplate | Templates aprovados: nome, id, variáveis, idioma |
| AuditEvent | Trilha: ação, `tenant_id`, timestamp, resultado |

---

## 14. Stack Tecnológica

| Componente | Tecnologia |
|---|---|
| Backend IA (`nexoia-agent`) | Python 3.11+, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic |
| Orquestração | LangGraph — runtime, checkpoints, state, subgraphs por capability |
| LLM | OpenAI API (GPT-4.1-mini) — intent, resposta, embeddings |
| Browser automation | Playwright Chromium (somente Hubla — sem API REST) |
| Banco de dados (`nexoia-infra`) | PostgreSQL 15 + pgvector — Docker Compose, volume persistente |
| Cache / Fila | Redis 7 — Docker Compose, dedup NX, mutex, circuit breaker |
| Painel operacional | ChatNexo — Node.js existente (`nexoia-panel`) |
| KB Admin Panel | React embutido no ChatNexo — upload, indexação, busca de teste |
| Canal WhatsApp | Meta Official API via ChatNexo + templates aprovados |
| Media Processing | Whisper (áudio), Vision API (imagem), `pypdf`/`python-docx` (PDF/DOCX) — no ChatNexo |

---

## 15. Roadmap da Fase 1

| Etapa | Escopo | Prazo |
|---|---|---|
| Etapa 0 — Foundation | `nexoia-infra`: Docker Compose com PostgreSQL + Redis. `nexoia-agent`: estrutura Clean Architecture, multi-tenant, autenticação | Sem. 1-2 |
| Etapa 1 — Webhook & Core | Webhook de compra, Proactive Welcome Capability, fila de mensagens, checkpoint LangGraph, Context Builder | Sem. 2-3 |
| Etapa 2 — KB Admin | Login, upload, chunking, indexação pgvector, busca de teste, multi-tenant | Sem. 3-4 |
| Etapa 3 — Access | Busca escalonada, link nominal, update email, fallback 3 tentativas | Sem. 4-5 |
| Etapa 4 — Refund & Retention | N1/N2, guards, prazo, deny, Art. 49, garantia condicional, multi-produto | Sem. 5-7 |
| Etapa 5 — Knowledge | RAG 3 tentativas, sinônimos, threshold, reformulação | Sem. 7-8 |
| Etapa 6 — Loja Express | Jornada 7 dias, templates D+1 a D+7, agente especialista | Sem. 8-9 |
| Etapa 7 — Integrações | Hubla automation, Cademi REST, templates Meta aprovados | Sem. 6-9 (paralelo) |
| Etapa 8 — Hardening | Testes, dedup stress, circuit breaker, observabilidade, documentação | Sem. 9-10 |

---

## 16. Riscos e Mitigações

| Risco | Impacto | Mitigação |
|---|---|---|
| Hubla sem API REST | Browser automation frágil — UI muda e quebra | Self-healing, múltiplos seletores, alerta de falha, fallback humano |
| Template Meta não aprovado | Mensagem fora da janela = bloqueio do número | Aprovar templates antes de ativar. Nunca enviar livre fora da janela |
| Regras no prompt | Reintroduz problema da Sofia legada | Regras como código Python testável, nunca instrução no LLM |
| Banco acoplado ao agente | Migrations e deploy ficam emaranhados | `nexoia-infra` separado. Backend conecta via env var |
| Mutex ausente | Jobs duplicados de reembolso = duplicata financeira | Guard 5 (mutex Redis) obrigatório antes de qualquer fila de reembolso |
| Webhook de compra sem dedup | Duas boas-vindas para o mesmo aluno | Redis NX por `purchase_id` antes de qualquer processamento |

---

## 17. Critérios de Aceite da Fase 1

52. Webhook de compra recebido → template de boas-vindas enviado em ≤ 60s  
53. Fluxo de acesso: busca escalonada + link nominal funcionando  
54. Refund & Retention: N1/N2 + guards + deny + Art. 49 testados  
55. KB Admin: upload → indexação → busca de teste funcionando  
56. Template Meta D+1 aprovado e enviado no follow-up de Loja Express  
57. Deduplicação: sem mensagens duplicadas em cenário de retry  
58. Mutex de reembolso: sem jobs duplicados para mesmo produto+contato  
59. Multi-tenant: tenant A não acessa dados do tenant B  
60. ChatNexo integrado ao backend Python bidirecionalmente  
61. `nexoia-infra`: PostgreSQL + Redis subindo via `docker-compose up`

---

## 18. Próximos Documentos

| Documento | Escopo | Prio |
|---|---|---|
| Spec — `nexoia-infra` | `docker-compose.yml`, schemas, volumes, migrations, seeds iniciais | P0 |
| Spec — Webhook de compra | Endpoint, payload, idempotência, template, fallbacks | P0 |
| Spec — Refund & Retention | N1/N2, guards, Art.49, deny, multi-produto completo | P0 |
| Spec — Access Capability | Link nominal, busca escalonada, update email, casos de borda | P0 |
| Spec — Integração Hubla | Playwright, workers, mutex, timeout, self-healing, MFA | P0 |
| Spec — KB Admin Panel | Wireframes, upload, indexação, auth multi-tenant | P1 |
| Spec — Templates Meta | Lista de templates, variáveis, aprovação, casos de uso | P1 |
| Spec — Conversation Core | LangGraph, checkpoint, Context Builder, memória longa | P1 |
| Spec — Knowledge/RAG | Chunking, sinônimos, threshold, reformulação, categorias | P1 |
| Spec — Loja Express | Jornada 7 dias, agente especialista, escalação operacional | P2 |
| Spec — Escalação | Catálogo de triggers: quando escalar e quando não escalar | P2 |
| Spec — Modelo de Dados | DDL completo, índices, migrations, `tenant_id` em todo domínio | P2 |

---

## Origem deste documento

Este PRD incorpora o conhecimento acumulado em 112 commits, 85 regras absolutas, 16 árvores de decisão e 952 testes da Sofia atual (G2 Educação), além das diretrizes do kickoff NexoIA (mar/2026) e do fluxograma V5.

As correções da v3.0 adicionam:

- fluxo proativo pós-compra via webhook
- separação do banco em repositório Docker independente
- conformidade completa com Clean Architecture + SOLID

**NexoIA PRD v3.0 | Abril 2026**