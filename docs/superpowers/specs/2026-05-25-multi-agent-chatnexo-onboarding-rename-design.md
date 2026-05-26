# Design: Multi-Atendentes ChatNexo + Rename Follow-up → Onboarding

**Data:** 2026-05-25
**Status:** Aprovado

---

## Visão Geral

Duas mudanças simultâneas:

1. **Multi-atendentes ChatNexo** — suporte a N chaves de API por conta, cada uma representando um atendente com nome próprio. O ChatNexo exibe o nome do atendente automaticamente ao enviar com uma chave específica. A seleção é aleatória nos disparos de onboarding e travada no atendente do último disparo recebido quando o usuário responde.

2. **Rename follow-up → onboarding** — renomeia tabelas, arquivos, classes, rotas e labels em toda a stack para o vocabulário correto do produto.

---

## 1. Banco de Dados

### 1.1 Nova tabela `chatnexo_agents`

```sql
CREATE TABLE chatnexo_agents (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id  INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    name        VARCHAR(120) NOT NULL,
    api_key_encrypted TEXT NOT NULL,
    is_active   BOOLEAN NOT NULL DEFAULT true,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (account_id, name)
);
CREATE INDEX ix_chatnexo_agents_account ON chatnexo_agents (account_id);
```

- `api_key_encrypted` usa Fernet (mesma chave `INTEGRATION_CREDENTIALS_KEY` usada em `integration_configs`)
- A chave única existente `chatnexo_api_key` em `accounts.settings` permanece como **fallback** — usada quando `chatnexo_agents` está vazio

### 1.2 Nova coluna em `conversations`

```sql
ALTER TABLE conversations
  ADD COLUMN last_onboarding_agent_id UUID
  REFERENCES chatnexo_agents(id) ON DELETE SET NULL;
```

Armazena qual atendente enviou o último step de onboarding para esta conversa. Usado para travar o atendente durante a resposta da IA.

### 1.3 Rename das 4 tabelas (migration separado)

| Antes | Depois |
|---|---|
| `followup_flows` | `onboarding_flows` |
| `followup_steps` | `onboarding_steps` |
| `followup_enrollments` | `onboarding_enrollments` |
| `followup_enrollment_steps` | `onboarding_enrollment_steps` |

O campo `job_queue.kind = "followup_step"` é mantido como string legada válida para não invalidar jobs já enfileirados em produção. O handler aceita ambos os valores (`"followup_step"` e `"onboarding_step"`) durante o período de transição.

---

## 2. Domínio

### 2.1 Nova entidade `ChatNexoAgent`

```python
# shared/domain/entities/chatnexo_agent.py
@dataclass(frozen=True)
class ChatNexoAgent:
    id: UUID
    name: str
    api_key: str
    is_active: bool
```

### 2.2 `IntegrationConfig` atualizado

```python
# shared/domain/entities/account_config.py
@dataclass(frozen=True)
class IntegrationConfig:
    ...  # campos existentes preservados
    chatnexo_agents: list[ChatNexoAgent] = field(default_factory=list)
```

`chatnexo_agents` carrega apenas agentes `is_active=True`, já decriptados.

### 2.3 Protocol de seleção de agente (SOLID — Open/Closed)

```python
# shared/domain/ports/agent_selection.py
class AgentSelectionStrategy(Protocol):
    def pick(self, agents: list[ChatNexoAgent]) -> ChatNexoAgent: ...
```

Implementação padrão:

```python
# shared/adapters/agent_selection/random_selection.py
class RandomAgentSelection:
    def pick(self, agents: list[ChatNexoAgent]) -> ChatNexoAgent:
        return random.choice(agents)
```

Amanhã, se necessário, `RoundRobinSelection` ou `WeightedSelection` implementam o mesmo Protocol sem tocar nos handlers.

### 2.4 Port do repositório de agentes (SOLID — Dependency Inversion)

```python
# shared/domain/ports/chatnexo_agent_repo.py
class ChatNexoAgentRepositoryPort(Protocol):
    async def list_active(self, account_id: int) -> list[ChatNexoAgent]: ...
    async def create(self, account_id: int, name: str, api_key: str) -> ChatNexoAgent: ...
    async def update(self, id: UUID, account_id: int, name: str | None, api_key: str | None) -> ChatNexoAgent: ...
    async def delete(self, id: UUID, account_id: int) -> None: ...
```

---

## 3. Adapters

### 3.1 `ChatNexoAgentRepository`

```python
# shared/adapters/db/repositories/chatnexo_agent_repo.py
@dataclass
class ChatNexoAgentRepository:
    session: AsyncSession
    fernet: Fernet

    async def list_active(self, account_id: int) -> list[ChatNexoAgent]: ...
    async def create(self, account_id: int, name: str, api_key: str) -> ChatNexoAgent: ...
    async def update(self, ...) -> ChatNexoAgent: ...
    async def delete(self, id: UUID, account_id: int) -> None: ...  # 404 se não encontrado
```

### 3.2 `ChatNexoClient` — novo factory method

```python
# shared/adapters/chatnexo/client.py
@classmethod
def with_key(cls, base_url: str, api_key: str) -> ChatNexoClient:
    client = httpx.AsyncClient(
        base_url=base_url,
        headers={"api_access_token": api_key},
        timeout=httpx.Timeout(10.0, connect=3.0),
    )
    return cls(http=client)
```

### 3.3 `ConversationRepository` — dois novos métodos

```python
async def get_last_onboarding_agent_id(self, conversation_id: int) -> UUID | None: ...
async def set_last_onboarding_agent_id(self, conversation_id: int, agent_id: UUID) -> None: ...
```

### 3.4 `AccountConfigRepository` — carrega agentes

O método `get(account_id)` passa a carregar `chatnexo_agents` ativos da nova tabela e os inclui em `IntegrationConfig.chatnexo_agents`.

---

## 4. Lógica de Seleção

Função utilitária central (SOLID — Single Responsibility):

```python
# shared/adapters/chatnexo/agent_picker.py

def build_chatnexo_client(
    base_url: str,
    agents: list[ChatNexoAgent],
    strategy: AgentSelectionStrategy,
    fallback_api_key: str,
) -> tuple[ChatNexoClient, UUID | None]:
    """
    Retorna (client, agent_id).
    agent_id é None quando usa o fallback da chave única.
    """
    if agents:
        agent = strategy.pick(agents)
        return ChatNexoClient.with_key(base_url, agent.api_key), agent.id
    return ChatNexoClient.with_key(base_url, fallback_api_key), None
```

### 4.1 Regras por contexto

| Contexto | Seleção | Persiste agent_id? |
|---|---|---|
| Disparo de step de onboarding | Aleatório | ✅ Salva em `conversations.last_onboarding_agent_id` |
| Resposta da IA (usuário escreveu) | `last_onboarding_agent_id` se existir, senão aleatório | ❌ |
| Lifecycle (idle ping / close) | Aleatório | ❌ |

---

## 5. Handlers — Alterações

### 5.1 `handlers/message.py` (`handle_message`)

```python
# Após carregar account_config:
last_agent_id = await conversation_repo.get_last_onboarding_agent_id(conversation_id)

if last_agent_id:
    agent = next((a for a in account_config.integration.chatnexo_agents if a.id == last_agent_id), None)
    if agent:
        chatnexo = ChatNexoClient.with_key(account_config.integration.chatnexo_base_url, agent.api_key)
    else:
        chatnexo, _ = build_chatnexo_client(base_url, agents, RandomAgentSelection(), fallback_key)
else:
    chatnexo, _ = build_chatnexo_client(base_url, agents, RandomAgentSelection(), fallback_key)
```

### 5.2 `handlers/scheduled.py` — step de onboarding

```python
chatnexo, agent_id = build_chatnexo_client(base_url, agents, RandomAgentSelection(), fallback_key)

# após envio bem-sucedido:
if agent_id:
    await conversation_repo.set_last_onboarding_agent_id(conversation_id, agent_id)
```

### 5.3 `lifecycle_handler.py`

```python
chatnexo, _ = build_chatnexo_client(base_url, agents, RandomAgentSelection(), fallback_key)
# sem persistência de agent_id
```

---

## 6. API Endpoints

Novo router: `interface/http/routers/admin/chatnexo_agents.py`

```
GET    /admin/chatnexo-agents           → list[AgentItem]   (api_key mascarada)
POST   /admin/chatnexo-agents           → AgentItem          201
PATCH  /admin/chatnexo-agents/{id}      → AgentItem          (name e/ou api_key)
DELETE /admin/chatnexo-agents/{id}      → 204
```

Schemas Pydantic:

```python
class AgentItem(BaseModel):
    id: UUID
    name: str
    api_key_masked: str  # ex: "nxia_****"
    is_active: bool
    created_at: datetime

class CreateAgentInput(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    api_key: str = Field(min_length=1)

class UpdateAgentInput(BaseModel):
    name: str | None = None
    api_key: str | None = None
```

---

## 7. Frontend

### 7.1 Nova seção em `/settings` — "Atendentes ChatNexo"

Componente `ChatNexoAgentsSection` adicionado à página de Settings, abaixo das integrações existentes:

- Lista de agentes: nome + chave mascarada + botão "Remover"
- Formulário inline: campo "Nome do atendente" + campo "API Key" + botão "Adicionar"
- Toast de sucesso/erro em cada operação
- A seção do campo `chatnexo_api_key` existente mantém um label explicativo: _"Chave de fallback — usada quando não há atendentes cadastrados"_

Novas funções em `src/lib/api.ts`:
```typescript
listChatnexoAgents(): Promise<AgentItem[]>
createChatnexoAgent(dto: CreateAgentInput): Promise<AgentItem>
updateChatnexoAgent(id: string, dto: UpdateAgentInput): Promise<AgentItem>
deleteChatnexoAgent(id: string): Promise<void>
```

### 7.2 Rename follow-up → onboarding (frontend)

| Antes | Depois |
|---|---|
| `/followup` | `/onboarding` (redirect 301 de `/followup`) |
| `/followup/[id]` | `/onboarding/[id]` |
| `features/followup/` | `features/onboarding/` |
| `useFollowupFlows` | `useOnboardingFlows` |
| `useFollowupSteps` | `useOnboardingSteps` |
| `FollowupFlow`, `FollowupStep` (types) | `OnboardingFlow`, `OnboardingStep` |
| `FlowCard`, `FlowDrawer` | mantidos (nomes genéricos, sem "followup") |
| Sidebar: "Follow-up" | "Onboarding" |
| `listFollowupFlows`, `createFollowupFlow`, etc. | `listOnboardingFlows`, `createOnboardingFlow`, etc. |
| Rotas da API: `/admin/followup/flows` | `/admin/onboarding/flows` |

---

## 8. Rename follow-up → onboarding (backend)

| Antes | Depois |
|---|---|
| `interface/http/routers/admin/followup.py` | `onboarding.py` |
| `interface/http/routers/admin/followup_enrollments.py` | `onboarding_enrollments.py` |
| `interface/http/schemas/followup.py` | `onboarding.py` |
| `shared/adapters/db/repositories/followup_flow_repo.py` | `onboarding_flow_repo.py` |
| `shared/adapters/db/repositories/followup_enrollment_repo.py` | `onboarding_enrollment_repo.py` |
| `shared/application/use_cases/followup/` | `use_cases/onboarding/` |
| `shared/domain/entities/followup.py` | `onboarding.py` |
| Classes `FollowupFlow`, `FollowupStep`, etc. | `OnboardingFlow`, `OnboardingStep`, etc. |
| Rotas HTTP `/admin/followup/` | `/admin/onboarding/` |
| `models.py`: `FollowupFlowModel`, etc. | `OnboardingFlowModel`, etc. |

**Exceção deliberada:** `job_queue.kind = "followup_step"` aceita ambos os valores durante transição:
```python
elif job_type in ("followup_step", "onboarding_step"):
    ...  # mesmo handler
```

---

## 9. Migrations (ordem de execução)

1. `XXXX_add_chatnexo_agents.py` — cria `chatnexo_agents` + coluna `conversations.last_onboarding_agent_id`
2. `XXXX_rename_followup_to_onboarding.py` — renomeia as 4 tabelas via `op.rename_table`

---

## 10. Critérios de Aceite

- [ ] CRUD de atendentes funciona via API e UI
- [ ] `is_active=False` exclui o atendente da seleção sem deletar do banco
- [ ] Fallback para chave única funciona quando lista está vazia
- [ ] Disparo de onboarding usa agente aleatório e salva em `last_onboarding_agent_id`
- [ ] Resposta da IA usa agente travado se `last_onboarding_agent_id` existir
- [ ] Lifecycle (ping/close) usa aleatório sem persistência
- [ ] Tabelas renomeadas — queries antigas retornam erro (confirmação de migration)
- [ ] Rotas antigas `/admin/followup/` → 404 (novas em `/admin/onboarding/`)
- [ ] Frontend sidebar mostra "Onboarding"
- [ ] Redirect 301 de `/followup` → `/onboarding` funciona
- [ ] Jobs com `kind="followup_step"` ainda são processados
