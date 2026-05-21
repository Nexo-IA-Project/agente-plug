# NexoIA — Follow-up Dinâmico por Curso (Design)

**Data:** 2026-05-08
**Branch:** `feat/dynamic-followup-meta-templates`
**Subsistemas afetados:** Follow-up Engine · Follow-up Flow Manager · Meta Template Manager · Loja Express (descontinuado) · Webhook Hubla
**Tipo:** Mudança estrutural (banco + API + UI + remoção de feature)

---

## 1. Resumo executivo

Hoje o motor de follow-up casa uma compra em um flow por meio de matching de string contra `FollowupFlow.product_tags`. A interface engessa o cadastro a esse modelo e o disparo via Loja Express é tratado por um caminho paralelo (`LojaExpressCase` + scheduled jobs específicos).

Esta mudança redesenha a base do follow-up em torno de uma nova entidade **Course**:

- **Course** passa a ser a chave de catálogo. Cada curso tem nome amigável e um `hubla_id` técnico que casa com o payload do webhook.
- Cada **FollowupFlow** vincula-se obrigatoriamente a um curso. Um curso pode ter N flows ativos; quando uma compra chega, todos os flows ativos do curso são programados — cada step seguindo seu próprio `delay_from_purchase_hours`.
- O caminho especial de **Loja Express** é descontinuado: vira um curso comum com flow seed contendo os 5 steps históricos (D+0/D+1/D+3/D+5/D+7).
- O step ganha um sistema de **variáveis dinâmicas**: para cada placeholder de template Meta o usuário escolhe a fonte do valor (nome do aluno, nome do curso, telefone, email) ou digita texto fixo.
- A **UI da listagem** perde a ordenação externa entre flows (não faz mais sentido); a ordenação que importa é a dos steps dentro do flow.
- O **modal centralizado** de cadastro/edição é substituído por um **drawer lateral** que entra da direita, encosta na linha da sidebar lateral do app e ocupa a área de conteúdo inteira — usado tanto na nova página de Cursos quanto na página de Follow-up.

Como a feature ainda não está em produção, não há migração de dados: a migration faz drop+recreate.

---

## 2. Motivação

1. **Catálogo explícito de cursos.** Hoje o "produto" é uma string solta (`product_tags` JSONB livre, sem validação). Isso torna inviável: (a) padronizar o disparo, (b) reaproveitar o nome do curso em variáveis de template, (c) ter uma UI clara sobre quais produtos estão configurados.
2. **Match estável com a Hubla.** A Hubla envia mais de um identificador no payload de venda. Tratar o nome do produto como chave é frágil — uma renomeação no painel quebra o follow-up. Um `hubla_id` técnico separado do `name` resolve isso.
3. **Loja Express deixou de ser exceção.** A capability original cresceu para representar um caso de venda como qualquer outro. Manter um caminho duplicado (case especial + flows configuráveis) é débito que se acumula a cada novo produto que precise de delays semelhantes.
4. **Personalização de mensagens.** Hoje `template_variables` guarda strings cruas. Sem ligação semântica com a compra, o admin precisa preencher manualmente o nome do aluno em cada step — o que não escala. Variáveis dinâmicas resolvem isso na hora do dispatch.
5. **UI atual é apertada.** O modal centralizado aguenta um único form curto, mas não comporta o cadastro de cursos e o editor inline de steps com fluência. Um drawer lateral grande dá espaço para crescer sem perder o contexto da listagem.

---

## 3. Escopo

### Está dentro

- Nova entidade `Course` com CRUD completo (model, repo, router, página admin).
- Refatoração de `FollowupFlow`: adiciona `course_id` (FK NOT NULL); remove `product_tags` e `position`.
- Snapshot de `customer_name` e `product_name` no enrollment (para resolver variáveis no dispatch).
- Sistema de variáveis dinâmicas em `FollowupStep.template_variables` com 4 fontes + static.
- Extensão do payload do webhook Hubla (`PurchasePayload`): novos campos `product_id`, `product_name`, renomeação de `name` para `customer_name`.
- Refatoração do `purchase_handler.py` para usar `Course.find_by_hubla_id` e enrollar em todos os flows ativos.
- Remoção de `LojaExpressCase`, tabela `loja_express_cases`, configs `LOJA_EXPRESS_*`, use cases e handlers correspondentes.
- Migration `f3a4b5c6d7e8` que: cria `courses`, drop+recreate `followup_*` (sem preservação de dados), drop `loja_express_cases`.
- Seed do curso "Loja Express" + flow padrão com 5 steps.
- UI nova: página `/admin/courses` + redesenho de `/admin/followup` com novo drawer lateral.
- Componente `Drawer` compartilhado em `apps/web/src/shared/components/`.

### Está fora

- Migração/preservação de dados existentes (rasgar e recriar foi confirmado).
- Mudanças em outras capabilities (welcome, refund, knowledge, access).
- Mudanças no módulo de templates Meta em si — apenas o consumo das variáveis muda.
- Substituição de variáveis em `message_text` (texto livre permanece sem placeholder).
- Internacionalização do catálogo (cursos têm um único `name` por enquanto).
- Histórico/auditoria das edições de Course.

---

## 4. Modelo de domínio

### 4.1 Nova entidade

```
Course
─ id: UUID (PK)
─ account_id: UUID (FK → accounts.id, indexed)
─ name: str(200)            — exibido na UI
─ hubla_id: str(200)        — casa com payload.product_id da Hubla
─ is_active: bool = True
─ created_at: datetime
─ updated_at: datetime
─ UNIQUE (account_id, hubla_id)
```

**Por que `hubla_id` em string?** A Hubla pode mudar o tipo do identificador (numérico, slug, UUID). Uma string cobre todos os casos sem migration adicional.

**Por que `is_active`?** Soft-disable evita ter que excluir um curso fisicamente quando ele sai do catálogo, preservando histórico de enrollments antigos sem violar FKs.

### 4.2 Mudanças em `FollowupFlow`

```
FollowupFlow
+ course_id: UUID (FK → courses.id, NOT NULL, indexed, ON DELETE RESTRICT)
- product_tags             (DROP)
- position                 (DROP — ordenação externa eliminada)
```

`ON DELETE RESTRICT`: a UI bloqueia a exclusão de um curso que tenha flows vinculados. O usuário precisa remover ou desativar os flows antes.

### 4.3 Mudanças em `FollowupEnrollment`

```
FollowupEnrollment
+ customer_name: str(200) — snapshot do nome do aluno na hora da compra
+ product_name: str(200)  — snapshot do nome do curso na hora da compra
```

Snapshots evitam que renomeações futuras de Course "mudem o passado" — o template enviado em D+3 mostra exatamente o nome que existia no momento da venda.

### 4.4 Mudanças em `FollowupStep.template_variables`

Schema antigo (string):
```jsonc
{ "1": "Olá Fabio", "2": "Curso de Marketing" }
```

Schema novo (objeto):
```jsonc
{
  "1": { "source": "customer_name" },
  "2": { "source": "product_name" },
  "3": { "source": "static", "value": "promoção limitada" }
}
```

**Sources suportadas no MVP:**

| `source`        | Origem do valor                         |
|-----------------|------------------------------------------|
| `customer_name` | `enrollment.customer_name`               |
| `product_name`  | `enrollment.product_name`                |
| `contact_phone` | `enrollment.contact.phone`               |
| `contact_email` | `enrollment.contact.email` (pode estar vazio) |
| `static`        | `value` literal armazenado no JSON       |

Validação: se `source != "static"`, o campo `value` deve estar ausente. Se `source == "static"`, `value` é obrigatório.

### 4.5 Tabelas removidas

- `loja_express_cases` — drop completo via migration. A capability vira um curso comum.

---

## 5. Comportamento — fluxo da compra

```
POST /webhook/purchase
  ↓
PurchaseHandler.handle()
  ↓
[1] Dedup webhook (Redis, TTL 24h)
[2] Cria/busca contact por (account_id, phone)
[3] Cria/abre conversa ChatNexo
[4] course = course_repo.find_active_by_hubla_id(account_id, payload.product_id)
        ├─ não encontrado → loga warning, retorna sem enrollar
        └─ encontrado     → segue
[5] flows = flow_repo.list_active_by_course(course.id)
[6] Para cada flow em flows:
        EnrollContact.execute(
            account_id, contact_id, conversation_id, contact_phone,
            purchase_id, flow_id=flow.id,
            customer_name=payload.customer_name,
            product_name=payload.product_name,
            purchase_time=payload.occurred_at,
        )
[7] Cria AccessCase (welcome D+1)  — comportamento atual mantido
```

Cada `EnrollContact.execute()` cria um enrollment próprio e agenda os steps no `job_queue` com seus delays. **Não há ordenação entre flows do mesmo curso** — cada flow corre paralelamente, cada step dispara no seu próprio horário programado.

`EnrollContact` deixa de fazer matching de produto (responsabilidade movida pra cima, no handler) e passa a receber o `flow_id` direto.

---

## 6. API

### 6.1 Novo router `/admin/courses`

| Método | Path | Body | Response | Notas |
|--------|------|------|----------|-------|
| GET | `/admin/courses` | — | `list[CourseResponse]` | Ordenado por `name` |
| POST | `/admin/courses` | `CreateCourseRequest` | `CourseResponse` (201) | 409 se `(account_id, hubla_id)` já existe |
| PUT | `/admin/courses/{id}` | `UpdateCourseRequest` | `CourseResponse` | Campos opcionais |
| DELETE | `/admin/courses/{id}` | — | 204 / 409 | 409 se houver flow vinculado |

```python
class CreateCourseRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    hubla_id: str = Field(min_length=1, max_length=200)
    is_active: bool = True

class UpdateCourseRequest(BaseModel):
    name: str | None = None
    hubla_id: str | None = None
    is_active: bool | None = None

class CourseResponse(BaseModel):
    id: UUID
    name: str
    hubla_id: str
    is_active: bool
    flow_count: int        # contador denormalizado para UI
    created_at: datetime
    updated_at: datetime
```

### 6.2 Mudanças em `/admin/followup/flows`

```python
# ANTES
class CreateFlowRequest:
    name: str
    product_tags: list[str]
    is_active: bool = True

# DEPOIS
class CreateFlowRequest:
    name: str
    course_id: UUID            # obrigatório
    is_active: bool = True
```

`UpdateFlowRequest` análogo: `course_id` opcional. `FollowupFlowResponse` ganha `course: CourseSummary` (id+name+hubla_id) embutido.

**Endpoints removidos:**
- `PATCH /admin/followup/flows/reorder` — ordenação externa não existe mais.

**Endpoints mantidos:**
- Listagem, CRUD individual, CRUD de steps, `PATCH /flows/{id}/steps/reorder`.

### 6.3 Mudanças em `/admin/followup/flows/{id}/steps`

```python
class StepVariableBinding(BaseModel):
    source: Literal["customer_name", "product_name", "contact_phone", "contact_email", "static"]
    value: str | None = None  # obrigatório se source == "static"

class CreateStepRequest(BaseModel):
    delay_from_purchase_hours: int = Field(ge=0)
    meta_template_name: str | None = None
    template_variables: dict[str, StepVariableBinding] = Field(default_factory=dict)
    message_text: str | None = None
    # validador cruzado: exatamente um entre meta_template_name e message_text
```

### 6.4 Webhook `POST /webhook/purchase`

Schema do payload (Pydantic) atualizado:

```python
# ANTES
class PurchasePayload(BaseModel):
    purchase_id: str
    account_id: UUID
    name: str             # nome do aluno
    email: str | None
    phone: str
    product: str          # nome/tag
    amount_brl: int
    occurred_at: datetime
    document: str | None

# DEPOIS
class PurchasePayload(BaseModel):
    purchase_id: str
    account_id: UUID
    customer_name: str    # renomeado de `name`
    email: str | None
    phone: str
    document: str | None
    product_id: str       # NOVO — chave de match com Course.hubla_id
    product_name: str     # NOVO — snapshot pra variável dinâmica
    amount_brl: int
    occurred_at: datetime
```

A Hubla envia muitos campos no payload real; pegamos só os que precisamos (id e nome do curso, nome do aluno, mais o que já era usado).

---

## 7. Frontend

### 7.1 Componente `Drawer` compartilhado

Arquivo: `apps/web/src/shared/components/Drawer.tsx`.

Comportamento:
- Posição absoluta. Encosta no topo, fundo e direita do viewport. À esquerda termina exatamente na linha da sidebar lateral do app (largura da sidebar definida por CSS variable já existente no design system NexoIA).
- Slide-in da direita: `transform: translateX(100% → 0)`, transição `~250ms ease-out`.
- Backdrop com `fade` 200ms cobrindo a área de conteúdo (sidebar permanece visível e clicável fora do drawer).
- Fecha com: clique no backdrop, `Esc`, botão "X" no header.
- Conteúdo interno em flex column ocupando 100% da área. O form interno não fica centralizado — usa toda a largura.
- Acessibilidade: `role="dialog"`, `aria-modal="true"`, foco preso no drawer, retorno de foco ao fechar.

Props:
```ts
interface DrawerProps {
  open: boolean;
  onClose: () => void;
  title: string;            // header do drawer
  children: React.ReactNode;
  footer?: React.ReactNode; // ações fixas no rodapé (opcional)
}
```

### 7.2 Página `/admin/courses` (nova)

- Header com título e botão "Novo curso" (abre drawer).
- Listagem em cards verticais ou tabela leve, mostrando: **Nome**, **`hubla_id`**, badge ativo/inativo, `flow_count`, ações (editar, excluir).
- Excluir mostra confirm dialog. Se a API responder 409 (flows vinculados), exibe toast com a contagem de flows e oferece atalho para `/admin/followup` filtrado por aquele curso.
- Drawer de criação/edição com 3 campos: `name`, `hubla_id`, toggle `is_active`.
- Entrada no menu da sidebar do admin: novo item **"Cursos"**, posicionado entre "Follow-up" e "Templates" (decisão de menu pode ser ajustada na implementação visual).

### 7.3 Página `/admin/followup` (redesenhada)

**Listagem:**
- Remove drag-and-drop externo (`dnd-kit` nesse nível desaparece).
- Cards exibem:
  - Nome do flow (header).
  - Chip do curso vinculado: **`{course.name}`** com `hubla_id` em tooltip.
  - Contador de steps (ex: "5 steps").
  - Toggle ativo/inativo + ações (editar, excluir).
- Botão "Novo Follow-up" → drawer.

**Drawer de Flow (substitui o `FlowDrawer` atual + modal):**
- Header: "Novo Follow-up" / "Editar Follow-up — {name}".
- Form principal:
  - Campo `name`.
  - **Select obrigatório de Curso** — popula da lista de cursos ativos.
    - Se não houver cursos cadastrados, mostra mensagem com link "Cadastre um curso primeiro" → abre `/admin/courses`.
  - Toggle `is_active`.
- Subseção **Steps** (inline, sem modal aninhado):
  - Lista de steps já cadastrados (drag-and-drop interno mantido — usa `PATCH /steps/reorder`).
  - Cada step exibe: posição, delay (badge formatado tipo "D+0", "D+1", "D+3"), template ou trecho do texto livre, ações (editar inline, remover).
  - Botão "Adicionar step" → expande form inline com:
    - `delay_from_purchase_hours` (input numérico com helper para horas/dias).
    - Toggle de tipo: **Template Meta** (default) ou **Texto livre**.
    - Se template: select de templates Meta da conta. Após escolher, **renderiza dinamicamente um campo por variável detectada** (ver 7.4).
    - Se texto livre: textarea sem placeholders.
- Footer: botões "Cancelar" e "Salvar".

### 7.4 Editor de variáveis dinâmicas

Comportamento ao escolher um template Meta:
1. Detecta variáveis no template Meta (regex `{{(\d+)}}` aplicada ao corpo do template — campo já disponível na lista de templates).
2. Para cada variável detectada (ex: `{{1}}`, `{{2}}`), renderiza um sub-form:

```
Variável {{1}}
[ Select ▾ ] Nome do aluno
            Nome do curso
            Telefone do aluno
            Email do aluno
            Texto fixo...
```

3. Se o usuário escolher **Texto fixo**, aparece um `<input>` adicional para o valor literal.
4. Salva o objeto `template_variables` conforme o schema definido em §4.4.

Edge cases:
- Trocar o template seleciona reseta todas as bindings (e dispara confirmação se já havia algo preenchido).
- Variáveis nunca mais detectadas (template foi atualizado e tinha menos vars) são silenciosamente removidas no save.

### 7.5 Atualização do API client TypeScript

Em `apps/web/src/lib/api.ts`, adicionar:
```
listCourses, createCourse, updateCourse, deleteCourse
```

E ajustar:
- `listFollowupFlows` (response inclui `course`).
- `createFollowupFlow`, `updateFollowupFlow` (body usa `course_id`).
- `createFollowupStep`, `updateFollowupStep` (body usa `template_variables` no novo schema).
- Remover `reorderFollowupFlows`.

### 7.6 Tipos TypeScript

Em `apps/web/src/features/courses/types.ts` (novo) e `apps/web/src/features/followup/types.ts` (atualizado):

```ts
export interface Course {
  id: string;
  name: string;
  hubla_id: string;
  is_active: boolean;
  flow_count: number;
  created_at: string;
  updated_at: string;
}

export type StepVariableSource =
  | "customer_name"
  | "product_name"
  | "contact_phone"
  | "contact_email"
  | "static";

export interface StepVariableBinding {
  source: StepVariableSource;
  value?: string;  // só quando source === "static"
}

export interface FollowupStep {
  id: string;
  flow_id: string;
  position: number;
  delay_from_purchase_hours: number;
  meta_template_name: string | null;
  template_variables: Record<string, StepVariableBinding>;
  message_text: string | null;
}

export interface FollowupFlow {
  id: string;
  name: string;
  is_active: boolean;
  course: { id: string; name: string; hubla_id: string };
  steps_count: number;
  created_at: string;
  updated_at: string;
}
```

---

## 8. Migration

### 8.1 Arquivo

`apps/api/migrations/versions/f3a4b5c6d7e8_dynamic_followup_by_course.py`
- `revision = 'f3a4b5c6d7e8'`
- `down_revision = 'e2f3a4b5c6d7'` (followup_flow_position)

### 8.2 Upgrade

```python
def upgrade():
    # 1. Criar tabela courses
    op.create_table(
        "courses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("hubla_id", sa.String(200), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"]),
        sa.UniqueConstraint("account_id", "hubla_id", name="uq_courses_account_hubla"),
    )
    op.create_index("ix_courses_account_id", "courses", ["account_id"])

    # 2. Limpar dados de follow-up existentes (rasgar e recriar)
    op.execute("DELETE FROM followup_enrollment_steps")
    op.execute("DELETE FROM followup_enrollments")
    op.execute("DELETE FROM followup_steps")
    op.execute("DELETE FROM followup_flows")

    # 3. Adicionar course_id NOT NULL em followup_flows e remover product_tags / position
    op.add_column(
        "followup_flows",
        sa.Column("course_id", postgresql.UUID(as_uuid=True), nullable=False),
    )
    op.create_foreign_key(
        "fk_followup_flows_course_id",
        "followup_flows", "courses", ["course_id"], ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_followup_flows_course_id", "followup_flows", ["course_id"])
    op.drop_column("followup_flows", "product_tags")
    op.drop_column("followup_flows", "position")

    # 4. Snapshots no enrollment
    op.add_column("followup_enrollments", sa.Column("customer_name", sa.String(200), nullable=False, server_default=""))
    op.add_column("followup_enrollments", sa.Column("product_name", sa.String(200), nullable=False, server_default=""))
    op.alter_column("followup_enrollments", "customer_name", server_default=None)
    op.alter_column("followup_enrollments", "product_name", server_default=None)

    # 5. Drop loja_express_cases (capability descontinuada)
    op.drop_table("loja_express_cases")
```

### 8.3 Downgrade

Implementação reversa: drop FKs/colunas adicionadas, recria `product_tags` (JSONB) e `position` (Integer) em `followup_flows`, recria `loja_express_cases` com schema original, drop `courses`. Os dados não voltam — downgrade é estrutural.

### 8.4 Seed do curso "Loja Express"

Arquivo separado de seed (`apps/api/scripts/seed_loja_express.py` ou função idempotente em startup):

```python
def seed_loja_express(account_id: UUID, session):
    course = Course(
        id=uuid4(), account_id=account_id,
        name="Loja Express", hubla_id="loja-express",
        is_active=True,
    )
    session.add(course)
    flow = FollowupFlow(
        id=uuid4(), account_id=account_id,
        course_id=course.id, name="Loja Express — sequência padrão",
        is_active=True,
    )
    session.add(flow)
    delays = [
        (0, "loja_express_d0"),
        (24, "loja_express_d1"),
        (72, "loja_express_d3"),
        (120, "loja_express_d5"),
        (168, "loja_express_d7"),
    ]
    for i, (hours, template) in enumerate(delays):
        session.add(FollowupStep(
            id=uuid4(), flow_id=flow.id, position=i,
            delay_from_purchase_hours=hours,
            meta_template_name=template,
            template_variables={"1": {"source": "customer_name"}},
        ))
```

Os nomes dos templates (`loja_express_d0`, `loja_express_d1`, ...) são placeholders desta spec. Antes de rodar o seed em produção, mapear para os nomes reais dos Meta templates já aprovados na conta WhatsApp Business. O seed é parametrizável e idempotente — se já existir curso com `hubla_id="loja-express"`, não duplica.

---

## 9. Configuração

### 9.1 Removido de `settings.py`

```
LOJA_EXPRESS_PRODUCT_TAGS
LOJA_EXPRESS_D1_DELAY_HOURS
LOJA_EXPRESS_D3_DELAY_HOURS
LOJA_EXPRESS_D5_DELAY_HOURS
LOJA_EXPRESS_D7_DELAY_HOURS
```

### 9.2 `.env.example`

Remover as chaves correspondentes; adicionar nada (a feature de Course usa só os settings já existentes).

---

## 10. Limpeza de código

Arquivos/módulos removidos:

- `apps/api/src/shared/application/use_cases/loja_express/` (diretório inteiro).
- `apps/api/src/shared/adapters/loja_express/` (cliente, se existir).
- `apps/api/src/shared/adapters/db/repositories/loja_express_case_repo.py`.
- Branch de Loja Express em `purchase_handler.py`.
- Handler de scheduled job `scheduled_loja_express` (no worker dispatcher).
- Schemas Pydantic relacionados (`LojaExpressCaseResponse`, etc).
- Testes correspondentes em `apps/api/tests/`.

Atualizações no `CLAUDE.md` na próxima rodada (não nesta spec):
- Remover entradas da tabela de skills/capabilities relacionadas a Loja Express.
- Atualizar lista de tabelas e jobs.
- Atualizar lista de subsistemas para refletir 10 subsistemas + nova entrada "Course Catalog".

---

## 11. Testes

### 11.1 Backend (`pytest`)

**Unit:**
- `CourseRepository` — CRUD, unique constraint, find_active_by_hubla_id.
- `EnrollContact` (refatorado) — não faz mais matching, recebe `flow_id`; aceita snapshots.
- Variável dinâmica resolver — para cada source, valida o valor extraído; static retorna o `value`.
- Validação de `StepVariableBinding` — source != static não pode ter `value`; source == static exige `value`.

**Integration:**
- `POST /admin/courses` — criação, conflict 409, list com `flow_count`.
- `DELETE /admin/courses/{id}` — 409 quando há flow vinculado.
- `POST /admin/followup/flows` — exige `course_id` válido, retorna `course` no response.
- `POST /webhook/purchase` — payload novo cria N enrollments (1 por flow ativo do curso).
- `POST /webhook/purchase` — `product_id` desconhecido não cria enrollment, mas não falha o webhook.
- Worker dispatch de `followup_step` — resolve variáveis dinâmicas corretamente com snapshot do enrollment.

**Garantias de remoção:**
- Importar módulos de Loja Express deve falhar (módulos removidos).
- `pytest tests/unit` e `pytest tests/integration` passam sem warnings de tabela órfã.

### 11.2 Frontend

- Página `/admin/courses` renderiza lista, abre drawer, salva, valida.
- Página `/admin/followup` mostra cards sem drag-and-drop externo, mostra chip do curso.
- Drawer compartilhado: animação, foco preso, fecha com Esc/backdrop.
- Editor de variáveis: ao trocar template, reseta bindings; ao escolher static, mostra input de value.

### 11.3 Manual

Smoke test pós-deploy:
1. Criar curso "Loja Express" via UI, conferir `hubla_id` igual ao webhook.
2. Criar flow vinculado ao curso, com 2 steps usando template Meta com 1 variável dinâmica (nome do aluno).
3. Disparar webhook de compra simulando `product_id = "loja-express"`.
4. Conferir no DB: 1 enrollment criado, 2 enrollment_steps agendados.
5. Avançar tempo (ou disparar manualmente o job) e verificar mensagem chegando no número de teste com nome do aluno preenchido corretamente.

---

## 12. Riscos e mitigações

| Risco | Mitigação |
|-------|-----------|
| Hubla muda formato do `product_id` futuramente | `hubla_id` é string; basta atualizar valor no Course via UI sem migration. |
| Templates Meta com variáveis novas após criação do step | Variáveis órfãs são removidas silenciosamente no save; faltantes ficam em branco no envio (template Meta rejeita o envio — vai cair no DLQ, observável). |
| Drop de Loja Express remove histórico de cases | Aceito (estamos em dev, sem dados em produção). Caso de auditoria pós-deploy: nenhum. |
| Drawer compartilhado pode quebrar em viewports estreitos | Largura mínima razoável (ex: 480px) com fallback para tela cheia em mobile (responsividade entra como ajuste fino na implementação). |
| Race condition: webhook chega antes do curso ser cadastrado | Handler loga warning e segue sem criar enrollment. Operação é monitorável via logs estruturados; admin pode reagendar manualmente se quiser. |
| Esquecer de seedar "Loja Express" pós-migration | Script de seed idempotente; documentar no runbook de deploy. |

---

## 13. Plano de implementação (alto nível)

A ordem detalhada de tasks é responsabilidade do plano de implementação (writing-plans). Como referência, os marcos lógicos são:

1. **Banco e domínio**: model `Course`, repos, migration, ajustes em modelos de follow-up, snapshots no enrollment, drop de Loja Express.
2. **Use cases e handlers**: refatorar `EnrollContact`, refatorar `purchase_handler` (lookup por `Course`, enrollment N-vezes), novo resolver de variáveis dinâmicas no dispatch.
3. **API**: router `/admin/courses`, ajustes em `/admin/followup/*`, schemas Pydantic.
4. **Webhook**: novo `PurchasePayload`.
5. **Frontend — fundação**: componente `Drawer` compartilhado, hooks/api do feature `courses`.
6. **Frontend — Cursos**: página `/admin/courses`.
7. **Frontend — Follow-up**: refatoração da página, novo card, drawer com select de curso, editor de variáveis dinâmicas.
8. **Seed e cleanup**: seed Loja Express, remover código morto, atualizar `CLAUDE.md`.
9. **Testes e CI**: cobrir unit + integration; rodar gates locais antes de PR.
10. **Code review e PR**: usar `superpowers:requesting-code-review`, abrir PR após aprovação.

---

## 14. Critérios de aceite

- [ ] `alembic upgrade heads` aplica a migration sem erros em banco vazio e em banco com schema anterior.
- [ ] CRUD de Cursos funcional via UI; validação de unique e RESTRICT operacionais.
- [ ] Criar follow-up sem curso vinculado é impossível pelo formulário e pela API.
- [ ] Webhook de compra com `product_id` cadastrado cria N enrollments (= N flows ativos).
- [ ] Webhook de compra com `product_id` desconhecido não cria enrollments e loga warning estruturado.
- [ ] Variáveis dinâmicas: enrollment com `customer_name="Fabio"` envia template com `{{1}}` substituído por "Fabio".
- [ ] Variável `static` envia exatamente o `value` configurado.
- [ ] `loja_express_cases` não existe mais no banco; nenhum import quebrado no código.
- [ ] Curso "Loja Express" + flow seed estão presentes após o deploy.
- [ ] Drawer abre da direita, ocupa do topo ao fundo, encosta na linha da sidebar lateral, fecha com Esc/backdrop, anima suavemente.
- [ ] `ruff check`, `mypy src`, `tsc --noEmit`, `pytest tests/unit` e `pytest tests/integration` passam.
- [ ] PR aberto com base em `feat/dynamic-followup-meta-templates`.
