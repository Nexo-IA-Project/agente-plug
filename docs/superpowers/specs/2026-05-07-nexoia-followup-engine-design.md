# NexoIA — Follow-up Engine: Motor de Sequências Pós-Compra Dinâmicas

**Data:** 2026-05-07  
**Status:** Aprovado  
**Subsistema:** C — Follow-up Engine (backend)  
**Depende de:** Spec ① Core, Spec ② Welcome (purchase_handler, scheduled_jobs)

---

## Visão Geral

Implementar o motor de follow-up dinâmico que, ao receber um webhook de compra, inscreve o contato numa sequência de mensagens WhatsApp configurável pelo admin. Cada passo da sequência referencia um template Meta aprovado e é disparado num horário calculado a partir da hora da compra. O Loja Express permanece intacto — este engine coexiste com ele.

**Princípio:** configuração zero no código. O admin define flows e steps no painel; o engine apenas os executa.

---

## Requisitos Funcionais

| # | Requisito |
|---|-----------|
| RF-FE01 | Quando um webhook de compra chega e o produto **não** é Loja Express, o sistema verifica se há um `FollowupFlow` ativo cujas `product_tags` intersectam as tags do produto |
| RF-FE02 | Se um flow é encontrado, cria-se uma `FollowupEnrollment` e snapshot imutável dos steps (`FollowupEnrollmentStep`) |
| RF-FE03 | Para cada enrollment step, agenda-se um `ScheduledJob` do tipo `FOLLOWUP_STEP` com `run_at = purchase_time + delay_from_purchase_hours` |
| RF-FE04 | Quando o job dispara, o worker chama `DispatchFollowupStep`: envia o template Meta via ChatNexo e grava a mensagem enviada em `messages` (histórico da conversa) |
| RF-FE05 | Mudanças no flow após a criação de uma enrollment não afetam steps já agendados (snapshot garante imutabilidade) |
| RF-FE06 | A sequência **nunca para** automaticamente por resposta do aluno — executa todos os steps agendados |
| RF-FE07 | Se nenhum flow ativo for encontrado para o produto, a compra é processada normalmente sem follow-up |
| RF-FE08 | Admin API: CRUD completo de `FollowupFlow` (criar, listar, editar nome/tags/status, deletar) |
| RF-FE09 | Admin API: CRUD de `FollowupStep` por flow (criar, listar, editar, deletar, reordenar) |
| RF-FE10 | Ao deletar/desativar um flow, enrollments existentes não são canceladas |

## Requisitos Não-Funcionais

| # | Requisito |
|---|-----------|
| RNF-FE01 | Clean Architecture: domain → application → adapters → interface (sem inversão de dependência) |
| RNF-FE02 | SOLID: use cases injetados via construtor, sem acoplamento a implementações concretas |
| RNF-FE03 | Repositórios seguem o padrão `@dataclass` com `session: AsyncSession` dos demais repos |
| RNF-FE04 | Novos job types adicionados ao enum `JobType` em `shared/domain/entities/scheduled_job.py` |
| RNF-FE05 | Todos os endpoints admin exigem JWT admin válido via `_require_admin` |
| RNF-FE06 | Testes unitários para `EnrollContact` e `DispatchFollowupStep` com mocks de repo/chatnexo/scheduler |

---

## Arquitetura

### Modelo de Dados (4 novas tabelas)

**`followup_flows`**
```python
class FollowupFlowModel(Base):
    __tablename__ = "followup_flows"
    id: Mapped[uuid.UUID] = _pk()
    account_id: Mapped[uuid.UUID]          # FK accounts
    name: Mapped[str]                       # ex: "Máquina de Vendas"
    product_tags: Mapped[list[str]]         # ex: ["maquina_de_vendas"]  — JSONB text[]
    is_active: Mapped[bool]                 # False = pausado
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]
```

**`followup_steps`**
```python
class FollowupStepModel(Base):
    __tablename__ = "followup_steps"
    id: Mapped[uuid.UUID] = _pk()
    flow_id: Mapped[uuid.UUID]              # FK followup_flows
    position: Mapped[int]                   # ordem de exibição (1-based)
    delay_from_purchase_hours: Mapped[int]  # horas após a compra (ex: 0, 1, 24, 48)
    meta_template_name: Mapped[str]         # nome exato do template aprovado na Meta
    template_variables: Mapped[dict]        # JSONB — variáveis do template
    created_at: Mapped[datetime]
```

**`followup_enrollments`**
```python
class FollowupEnrollmentModel(Base):
    __tablename__ = "followup_enrollments"
    id: Mapped[uuid.UUID] = _pk()
    account_id: Mapped[uuid.UUID]
    flow_id: Mapped[uuid.UUID]              # FK followup_flows (referência histórica)
    contact_id: Mapped[uuid.UUID]           # FK contacts
    conversation_id: Mapped[uuid.UUID]      # FK conversations
    purchase_event_id: Mapped[uuid.UUID]    # FK webhook_events
    status: Mapped[str]                     # "active" | "completed" | "cancelled"
    created_at: Mapped[datetime]
```

**`followup_enrollment_steps`** (snapshot imutável)
```python
class FollowupEnrollmentStepModel(Base):
    __tablename__ = "followup_enrollment_steps"
    id: Mapped[uuid.UUID] = _pk()
    enrollment_id: Mapped[uuid.UUID]        # FK followup_enrollments
    position: Mapped[int]
    delay_from_purchase_hours: Mapped[int]  # copiado do step original
    meta_template_name: Mapped[str]         # copiado do step original
    template_variables: Mapped[dict]        # copiado do step original
    scheduled_job_id: Mapped[uuid.UUID | None]  # FK scheduled_jobs
    status: Mapped[str]                     # "pending" | "sent" | "failed"
    sent_at: Mapped[datetime | None]
```

---

### Camada de Domínio

**`shared/domain/entities/followup.py`**
```python
@dataclass
class FollowupFlow:
    id: UUID; account_id: UUID; name: str
    product_tags: list[str]; is_active: bool; created_at: datetime; updated_at: datetime

@dataclass
class FollowupStep:
    id: UUID; flow_id: UUID; position: int
    delay_from_purchase_hours: int
    meta_template_name: str; template_variables: dict; created_at: datetime

@dataclass
class FollowupEnrollment:
    id: UUID; account_id: UUID; flow_id: UUID
    contact_id: UUID; conversation_id: UUID
    purchase_event_id: UUID; status: str; created_at: datetime

@dataclass
class FollowupEnrollmentStep:
    id: UUID; enrollment_id: UUID; position: int
    delay_from_purchase_hours: int
    meta_template_name: str; template_variables: dict
    scheduled_job_id: UUID | None; status: str; sent_at: datetime | None
```

**`shared/domain/ports/followup.py`** (interfaces)
```python
class FollowupFlowPort(Protocol):
    async def find_active_by_product_tags(self, account_id: UUID, tags: list[str]) -> FollowupFlow | None: ...
    async def get_steps(self, flow_id: UUID) -> list[FollowupStep]: ...

class FollowupEnrollmentPort(Protocol):
    async def create(self, enrollment: FollowupEnrollment, steps: list[FollowupEnrollmentStep]) -> None: ...
    async def find_step_by_job_id(self, job_id: UUID) -> FollowupEnrollmentStep | None: ...
    async def update_step(self, step: FollowupEnrollmentStep) -> None: ...
    async def all_steps_sent(self, enrollment_id: UUID) -> bool: ...
    async def update_enrollment_status(self, enrollment_id: UUID, status: str) -> None: ...
```

---

### Camada de Aplicação

**`shared/application/use_cases/followup/enroll_contact.py`**

```python
class EnrollContact:
    def __init__(self, flow_repo, enrollment_repo, scheduler): ...

    async def execute(
        self, *, account_id, contact_id, conversation_id,
        purchase_event_id, product_tags: list[str], purchase_time: datetime
    ) -> FollowupEnrollment | None:
        flow = await self._flow_repo.find_active_by_product_tags(account_id, product_tags)
        if flow is None:
            return None

        steps = await self._flow_repo.get_steps(flow.id)
        enrollment = FollowupEnrollment(id=uuid4(), ..., status="active")
        enrollment_steps = []

        for step in steps:
            run_at = purchase_time + timedelta(hours=step.delay_from_purchase_hours)
            job = await self._scheduler.schedule(
                job_type=JobType.FOLLOWUP_STEP,
                account_id=account_id,
                conversation_id=conversation_id,
                run_at=run_at,
                payload={},  # enrollment_step_id preenchido após criação
            )
            enrollment_steps.append(FollowupEnrollmentStep(
                ..., scheduled_job_id=job.id, status="pending"
            ))

        await self._enrollment_repo.create(enrollment, enrollment_steps)
        return enrollment
```

**`shared/application/use_cases/followup/dispatch_followup_step.py`**

```python
class DispatchFollowupStep:
    def __init__(self, enrollment_repo, chatnexo, message_repo): ...

    async def execute(self, *, enrollment_step_id, account_id, conversation_id) -> str:
        step = await self._enrollment_repo.find_step(enrollment_step_id)
        if step is None or step.status != "pending":
            return "IGNORADO"

        await self._chatnexo.send_template(
            account_id=str(account_id),
            conversation_id=str(conversation_id),
            template_name=step.meta_template_name,
            variables=step.template_variables,
        )

        # Grava no histórico da conversa para a IA ter contexto
        await self._message_repo.save_outbound(
            conversation_id=conversation_id,
            content=f"[follow-up] template: {step.meta_template_name}",
            metadata={"followup_enrollment_step_id": str(step.id)},
        )

        step.status = "sent"
        step.sent_at = datetime.now(UTC)
        await self._enrollment_repo.update_step(step)

        if await self._enrollment_repo.all_steps_sent(step.enrollment_id):
            await self._enrollment_repo.update_enrollment_status(step.enrollment_id, "completed")

        return "SENT"
```

---

### Integração com Purchase Handler

```python
# shared/application/purchase_handler.py — após bloco Loja Express

if not is_loja_express and self._enroll_contact_uc is not None:
    await self._enroll_contact_uc.execute(
        account_id=UUID(account_id),
        contact_id=contact.id,
        conversation_id=UUID(conversation_id),
        purchase_event_id=event.id,
        product_tags=event.product_tags,
        purchase_time=event.occurred_at,
    )
```

`PurchaseHandler.__init__` ganha `enroll_contact_uc: Any = None` (OCP — não quebra injeção existente).

---

### Integração com Worker

**`shared/domain/entities/scheduled_job.py`**
```python
class JobType(str, Enum):
    # ... existentes ...
    FOLLOWUP_STEP = "FOLLOWUP_STEP"
```

**`interface/worker/handlers/scheduled.py`**
```python
elif job_type == JobType.FOLLOWUP_STEP:
    dispatch = _get_dispatch_followup_handler()
    await dispatch.execute(
        enrollment_step_id=UUID(payload["enrollment_step_id"]),
        account_id=UUID(payload["account_id"]),
        conversation_id=UUID(payload["conversation_id"]),
    )
```

---

### Admin API

**`interface/http/routers/admin/followup.py`**

```
GET    /admin/followup/flows                         → lista flows do account
POST   /admin/followup/flows                         → cria flow {name, product_tags}
PUT    /admin/followup/flows/{flow_id}               → edita {name, product_tags, is_active}
DELETE /admin/followup/flows/{flow_id}               → remove flow (soft: desativa)

GET    /admin/followup/flows/{flow_id}/steps         → lista steps ordenados por position
POST   /admin/followup/flows/{flow_id}/steps         → adiciona step
PUT    /admin/followup/flows/{flow_id}/steps/{sid}   → edita step
DELETE /admin/followup/flows/{flow_id}/steps/{sid}   → remove step
PATCH  /admin/followup/flows/{flow_id}/steps/reorder → reordena [{id, position}]
```

Todos os endpoints protegidos por `_require_admin`.

---

## Arquivos

### Novos
```
apps/api/src/shared/domain/entities/followup.py
apps/api/src/shared/domain/ports/followup.py
apps/api/src/shared/application/use_cases/followup/__init__.py
apps/api/src/shared/application/use_cases/followup/enroll_contact.py
apps/api/src/shared/application/use_cases/followup/dispatch_followup_step.py
apps/api/src/shared/adapters/db/repositories/followup_repo.py
apps/api/src/interface/http/routers/admin/followup.py
apps/api/src/interface/http/schemas/followup.py
apps/api/migrations/versions/xxxx_add_followup_tables.py
apps/api/tests/unit/use_cases/followup/test_enroll_contact.py
apps/api/tests/unit/use_cases/followup/test_dispatch_followup_step.py
apps/api/tests/unit/interface/admin/test_followup_router.py
```

### Modificados
```
apps/api/src/shared/domain/entities/scheduled_job.py   + JobType.FOLLOWUP_STEP
apps/api/src/shared/application/purchase_handler.py    + enroll_contact_uc
apps/api/src/interface/worker/handlers/scheduled.py    + case FOLLOWUP_STEP
apps/api/src/main.py                                   + DI de enroll/dispatch + router
```

---

## Fora de Escopo

- UI de gestão de flows/steps → Spec B
- Criação de templates Meta → Spec A
- Cancelamento manual de enrollment via UI → v2
- Relatório de envios (quantos alunos por step) → v2
