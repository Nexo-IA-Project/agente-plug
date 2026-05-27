# Step Sequence Refinement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refinar o passo 3 (Mensagens) do FlowDrawer com conectores visuais, label contextual, campo de tempo ergonômico, drag-handle persistente, numeração 1+ e cálculo de delay relativo do step anterior (vs absoluto desde o gatilho).

**Architecture:** 4 fases independentes. Fase 1 muda backend (rename de campo `delay_from_purchase_minutes` → `delay_from_previous_minutes`, refactor de `enroll_contact` e `resync_enrollment`, migration). Fase 2 estende `triggerEvents.ts` com `triggerVerb` e cria o helper `formatRelativeDelay`. Fase 3 cria componentes novos (`StepConnector`, `TimeInputGroup`) e refatora `StepItem`/`StepInlineForm`/`StepList`/`DelayBadge`. Fase 4 valida ponta-a-ponta.

**Tech Stack:** Next.js 15 (App Router), React, Tailwind, FastAPI, SQLAlchemy 2.0, Alembic, pytest.

**Spec:** `docs/superpowers/specs/2026-05-27-step-sequence-refinement-design.md`

**Branch:** `feat/step-sequence-and-media` (já criada, spec já commitada em `5b35915`). **Mesma branch** vai receber a Spec B depois.

---

## Fase 1 — Backend: rename do campo + cálculo relativo + migration

### Task 1: Rename do campo no modelo + entity

**Files:**
- Modify: `apps/api/src/shared/adapters/db/models.py` (linhas 516–533 e 565–575)
- Modify: `apps/api/src/shared/domain/entities/onboarding.py`

- [ ] **Step 1: Renomear coluna em `OnboardingStepModel`**

Em `apps/api/src/shared/adapters/db/models.py`, localize o bloco da `OnboardingStepModel` (perto da linha 516):

```python
class OnboardingStepModel(Base):
    __tablename__ = "onboarding_steps"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    flow_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("onboarding_flows.id"), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    delay_from_purchase_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # ...
```

Trocar `delay_from_purchase_minutes` por `delay_from_previous_minutes` (mantendo tipo e default). Idem no bloco `OnboardingEnrollmentStepModel` (perto da linha 565).

- [ ] **Step 2: Renomear no entity**

Em `apps/api/src/shared/domain/entities/onboarding.py`, procurar a dataclass do step (provavelmente `OnboardingStep` e `OnboardingEnrollmentStep`):

```bash
grep -n "delay_from_purchase_minutes" /home/fabio/www/agente-plug/apps/api/src/shared/domain/entities/onboarding.py
```

Renomear todas as ocorrências de `delay_from_purchase_minutes` → `delay_from_previous_minutes` neste arquivo.

- [ ] **Step 3: Commit**

```bash
git add apps/api/src/shared/adapters/db/models.py apps/api/src/shared/domain/entities/onboarding.py
git commit -m "refactor(onboarding): rename delay_from_purchase_minutes → delay_from_previous_minutes (model + entity)"
```

> Após este commit os testes vão **quebrar** propositalmente. As próximas tasks corrigem em cascata.

---

### Task 2: Rename em use cases + cálculo relativo de scheduled_at

**Files:**
- Modify: `apps/api/src/shared/application/use_cases/onboarding/enroll_contact.py`
- Modify: `apps/api/src/shared/application/use_cases/onboarding/resync_enrollment.py`
- Modify: `apps/api/src/shared/application/use_cases/onboarding/diff_flow_steps.py`

- [ ] **Step 1: Refactor `enroll_contact.py`**

Localizar o bloco que calcula `run_at` (linhas ~95–105):

```python
# ANTES:
for step in flow_steps:
    run_at = purchase_time + timedelta(minutes=step.delay_from_purchase_minutes)
    # ... cria scheduled_job ...
    repo.save_enrollment_step(
        # ...
        delay_from_purchase_minutes=step.delay_from_purchase_minutes,
        # ...
    )
```

Trocar para:

```python
# DEPOIS:
base_time = purchase_time
ordered_steps = sorted(flow_steps, key=lambda s: s.position)
for step in ordered_steps:
    base_time = base_time + timedelta(minutes=step.delay_from_previous_minutes)
    run_at = base_time
    # ... cria scheduled_job ...
    repo.save_enrollment_step(
        # ...
        delay_from_previous_minutes=step.delay_from_previous_minutes,
        # ...
    )
```

- [ ] **Step 2: Refactor `resync_enrollment.py` (2 ocorrências)**

Mesmo padrão — duas instâncias do cálculo (linhas ~65 e ~85). Substituir cada uma por:

```python
# bloco antes do loop:
base_time = enrollment.purchase_time
ordered = sorted(fs_list, key=lambda fs: fs.position)
# dentro do loop:
base_time = base_time + timedelta(minutes=fs.delay_from_previous_minutes)
run_at = base_time
```

Atualizar referências a `delay_from_purchase_minutes` → `delay_from_previous_minutes` em todas as chamadas a `save_enrollment_step` / `save_step` do arquivo.

- [ ] **Step 3: Refactor `diff_flow_steps.py`**

Linha 40 troca:

```python
delay_changed = enr.delay_from_previous_minutes != fs.delay_from_previous_minutes
```

- [ ] **Step 4: Commit**

```bash
git add apps/api/src/shared/application/use_cases/onboarding/
git commit -m "refactor(onboarding): scheduled_at agora é cumulativo a partir do step anterior"
```

---

### Task 3: Rename em schemas Pydantic + bug fix da posição

**Files:**
- Modify: `apps/api/src/interface/http/schemas/onboarding.py`
- Modify: `apps/api/src/interface/http/routers/admin/onboarding.py` (linha 253)

- [ ] **Step 1: Localizar schemas relevantes**

```bash
grep -n "delay_from_purchase_minutes\|delay_from_previous_minutes\|position" /home/fabio/www/agente-plug/apps/api/src/interface/http/schemas/onboarding.py
```

- [ ] **Step 2: Renomear campo em `CreateStepRequest`, `UpdateStepRequest`, `StepResponse`**

Para cada classe que tem `delay_from_purchase_minutes`, trocar por `delay_from_previous_minutes`. Adicionar validação no campo:

```python
class CreateStepRequest(BaseModel):
    position: int | None = Field(default=None, ge=1)
    delay_from_previous_minutes: int = Field(default=0, ge=0, le=525600)  # max 365 dias
    # ... outros campos ...
```

Aplicar a mesma validação (`ge=0, le=525600`) no `UpdateStepRequest`.

- [ ] **Step 3: Fix do bug "position começa em 0" no router**

Em `apps/api/src/interface/http/routers/admin/onboarding.py`, localizar a linha 253:

```python
# ANTES:
position = body.position if body.position is not None else len(existing)
# DEPOIS:
position = body.position if body.position is not None else len(existing) + 1
```

Atualizar também referências a `delay_from_purchase_minutes` nesse arquivo (`body.delay_from_purchase_minutes` → `body.delay_from_previous_minutes`).

- [ ] **Step 4: Rodar lint**

```bash
cd apps/api && uv run ruff check src
```

Esperado: All checks passed.

- [ ] **Step 5: Commit**

```bash
git add apps/api/src/interface/http/schemas/onboarding.py apps/api/src/interface/http/routers/admin/onboarding.py
git commit -m "feat(onboarding): position começa em 1 + valida delay_from_previous_minutes (0..525600)"
```

---

### Task 4: Atualizar testes existentes que usavam o nome antigo

**Files:**
- Modify: `apps/api/tests/unit/use_cases/onboarding/*.py` (todos os arquivos com `delay_from_purchase_minutes`)
- Modify: `apps/api/tests/unit/followup/*.py` (se houver)
- Modify: outros testes que referenciam o campo

- [ ] **Step 1: Listar todos os arquivos com o nome antigo**

```bash
grep -rln "delay_from_purchase_minutes" /home/fabio/www/agente-plug/apps/api/tests
```

- [ ] **Step 2: Substituir em massa**

```bash
cd /home/fabio/www/agente-plug && find apps/api/tests -name "*.py" -exec sed -i 's/delay_from_purchase_minutes/delay_from_previous_minutes/g' {} +
```

- [ ] **Step 3: Atualizar testes que assumem cálculo absoluto**

Procurar especificamente testes em `tests/unit/use_cases/onboarding/test_enroll_contact*.py` e `test_resync_enrollment*.py`. Os asserts de `run_at` esperavam:

```python
# ANTES (absoluto): run_at_step_2 == purchase_time + timedelta(minutes=2880)
# DEPOIS (relativo): se step1 tem delay=0 e step2 tem delay=2880, run_at_step_2 == purchase_time + 0 + 2880
```

Em geral, os testes que setavam `delay_from_purchase_minutes=2880` no step 2 (esperando D+2 absoluto) precisam ajustar pra: step 1 com `delay=0`, step 2 com `delay=2880`, step 3 com `delay=1440` (resultando run_at = T+0, T+2d, T+3d).

Ler cada teste, ajustar valores conforme a nova semântica relativa, e garantir que os asserts de `run_at` continuam fazendo sentido.

- [ ] **Step 4: Rodar testes**

```bash
cd apps/api && uv run pytest tests/unit/use_cases/onboarding/ -v 2>&1 | tail -30
```

Esperado: tudo passa. Se alguma assertion falhar com `run_at` diferente, ajustar o valor esperado conforme cálculo cumulativo.

- [ ] **Step 5: Rodar suite completa pra validar non-regression**

```bash
cd apps/api && uv run pytest tests/unit -q 2>&1 | tail -5
```

Esperado: todos passam.

- [ ] **Step 6: Commit**

```bash
git add apps/api/tests
git commit -m "test(onboarding): atualiza fixtures para delay_from_previous_minutes (relativo)"
```

---

### Task 5: Migration Alembic

**Files:**
- Create: `apps/api/migrations/versions/<rev>_step_delay_relative_and_position_one_indexed.py`

- [ ] **Step 1: Gerar revision file**

```bash
cd apps/api && uv run alembic revision -m "step delay relative and position one indexed"
```

Anotar o `<rev>` gerado. Confirmar `down_revision` aponta para o head atual:

```bash
uv run alembic heads
```

- [ ] **Step 2: Implementar `upgrade()` e `downgrade()`**

Editar o arquivo gerado em `apps/api/migrations/versions/<rev>_step_delay_relative_and_position_one_indexed.py`:

```python
"""step delay relative and position one indexed

Revision ID: <rev>
Revises: <previous_head>
Create Date: 2026-05-27

Renomeia delay_from_purchase_minutes → delay_from_previous_minutes em onboarding_steps
e onboarding_enrollment_steps, convertendo valores absolutos pra relativos
(diff do step anterior). Também migra position 0-indexed → 1-indexed.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "<rev>"
down_revision = "<previous_head>"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Adiciona coluna nova com default 0
    op.add_column(
        "onboarding_steps",
        sa.Column(
            "delay_from_previous_minutes",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "onboarding_enrollment_steps",
        sa.Column(
            "delay_from_previous_minutes",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )

    conn = op.get_bind()

    # 2. Converte absolutos em relativos (por flow_id ou enrollment_id, ordenado por position)
    for table, parent_col in (
        ("onboarding_steps", "flow_id"),
        ("onboarding_enrollment_steps", "enrollment_id"),
    ):
        rows = conn.execute(
            sa.text(
                f"SELECT id, {parent_col}, position, delay_from_purchase_minutes "
                f"FROM {table} ORDER BY {parent_col}, position"
            )
        ).fetchall()
        prev_by_parent: dict = {}
        for r in rows:
            parent = getattr(r, parent_col)
            prev = prev_by_parent.get(parent, 0)
            relative = max(0, r.delay_from_purchase_minutes - prev)
            conn.execute(
                sa.text(
                    f"UPDATE {table} SET delay_from_previous_minutes = :rel WHERE id = :id"
                ),
                {"rel": relative, "id": r.id},
            )
            prev_by_parent[parent] = r.delay_from_purchase_minutes

    # 3. Corrige position zero-indexed em flows/enrollments que ainda têm position=0
    conn.execute(
        sa.text(
            """
            UPDATE onboarding_steps SET position = position + 1
            WHERE flow_id IN (
                SELECT DISTINCT flow_id FROM onboarding_steps WHERE position = 0
            )
            """
        )
    )
    conn.execute(
        sa.text(
            """
            UPDATE onboarding_enrollment_steps SET position = position + 1
            WHERE enrollment_id IN (
                SELECT DISTINCT enrollment_id FROM onboarding_enrollment_steps WHERE position = 0
            )
            """
        )
    )

    # 4. Dropa coluna antiga
    op.drop_column("onboarding_steps", "delay_from_purchase_minutes")
    op.drop_column("onboarding_enrollment_steps", "delay_from_purchase_minutes")


def downgrade() -> None:
    # 1. Recria coluna antiga
    op.add_column(
        "onboarding_steps",
        sa.Column(
            "delay_from_purchase_minutes",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "onboarding_enrollment_steps",
        sa.Column(
            "delay_from_purchase_minutes",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )

    conn = op.get_bind()

    # 2. Reconstrói absoluto via soma cumulativa
    for table, parent_col in (
        ("onboarding_steps", "flow_id"),
        ("onboarding_enrollment_steps", "enrollment_id"),
    ):
        rows = conn.execute(
            sa.text(
                f"SELECT id, {parent_col}, position, delay_from_previous_minutes "
                f"FROM {table} ORDER BY {parent_col}, position"
            )
        ).fetchall()
        cumulative_by_parent: dict = {}
        for r in rows:
            parent = getattr(r, parent_col)
            cum = cumulative_by_parent.get(parent, 0) + r.delay_from_previous_minutes
            conn.execute(
                sa.text(
                    f"UPDATE {table} SET delay_from_purchase_minutes = :abs WHERE id = :id"
                ),
                {"abs": cum, "id": r.id},
            )
            cumulative_by_parent[parent] = cum

    # 3. Reverte position (1-indexed → 0-indexed)
    conn.execute(sa.text("UPDATE onboarding_steps SET position = position - 1 WHERE position > 0"))
    conn.execute(
        sa.text("UPDATE onboarding_enrollment_steps SET position = position - 1 WHERE position > 0")
    )

    op.drop_column("onboarding_steps", "delay_from_previous_minutes")
    op.drop_column("onboarding_enrollment_steps", "delay_from_previous_minutes")
```

Substituir `<rev>` e `<previous_head>` pelos valores reais que o alembic preencheu.

- [ ] **Step 3: Subir postgres e rodar migration**

```bash
docker compose up -d postgres 2>&1 | tail -3
cd apps/api && uv run alembic upgrade heads
```

Esperado: sem erro. Output deve mencionar a revision nova.

- [ ] **Step 4: Validar dados no banco (smoke)**

```bash
docker compose exec -T postgres psql -U postgres -d agente_plug -c "
  SELECT flow_id, position, delay_from_previous_minutes
  FROM onboarding_steps ORDER BY flow_id, position LIMIT 10;
"
```

Verificar visualmente que valores fazem sentido (0 no primeiro de cada flow, somatórios coerentes nos seguintes).

Se o banco está vazio em dev (sem steps cadastrados), a migration ainda é válida — apenas roda o `op.add_column` e `op.drop_column`.

- [ ] **Step 5: Testar downgrade e re-upgrade (idempotência básica)**

```bash
cd apps/api && uv run alembic downgrade -1
cd apps/api && uv run alembic upgrade heads
```

Sem erro em ambos.

- [ ] **Step 6: Commit**

```bash
git add apps/api/migrations/versions/<rev>_step_delay_relative_and_position_one_indexed.py
git commit -m "feat(onboarding): migration delay relativo + position 1-indexed"
```

---

## Fase 2 — Frontend libs/helpers

### Task 6: Adicionar `triggerVerb` em `triggerEvents.ts`

**Files:**
- Modify: `apps/web/src/features/onboarding/lib/triggerEvents.ts`

- [ ] **Step 1: Adicionar campo `triggerVerb` na interface**

Localizar a `interface TriggerEventMeta` no arquivo. Adicionar:

```ts
export interface TriggerEventMeta {
  value: HublaEventType;
  label: string;
  pillLabel?: string;
  technical: string;
  description: string;
  category: HublaEventCategory;
  categoryLabel: string;
  icon: string;
  tone: TriggerEventTone;
  /**
   * Frase que completa "Assim que [triggerVerb]" — usada no DelayBadge do 1º step.
   * Exemplo: "a venda for ativada", "o carrinho for abandonado".
   */
  triggerVerb: string;
}
```

- [ ] **Step 2: Adicionar `triggerVerb` em todas as 25 entries**

Para cada entry em `TRIGGER_EVENTS`, adicionar campo `triggerVerb` antes do fechamento. Tabela:

| event_type | triggerVerb |
|---|---|
| `lead.abandoned_cart` | `"o carrinho for abandonado"` |
| `member.access_granted` | `"o acesso for concedido"` |
| `member.access_removed` | `"o acesso for removido"` |
| `subscription.created` | `"a venda for criada"` |
| `subscription.activated` | `"a venda for ativada"` |
| `subscription.expired` | `"a assinatura expirar"` |
| `subscription.deactivated` | `"a assinatura for cancelada"` |
| `subscription.auto_renewal_disabled` | `"a renovação automática for desligada"` |
| `subscription.auto_renewal_enabled` | `"a renovação automática for reativada"` |
| `invoice.created` | `"a fatura for emitida"` |
| `invoice.status_updated` | `"o status da fatura mudar"` |
| `invoice.payment_completed` | `"o pagamento for confirmado"` |
| `invoice.payment_failed` | `"o pagamento falhar"` |
| `invoice.expired` | `"a fatura vencer"` |
| `invoice.refunded` | `"a fatura for reembolsada"` |
| `installment.created` | `"o parcelamento for criado"` |
| `installment.failed` | `"a cobrança de parcela falhar"` |
| `installment.in_progress` | `"o parcelamento estiver em andamento"` |
| `installment.overdue` | `"uma parcela atrasar"` |
| `installment.cancelled` | `"o parcelamento for cancelado"` |
| `installment.completed` | `"o parcelamento for concluído"` |
| `refund_request.created` | `"o cliente pedir reembolso"` |
| `refund_request.accepted` | `"o reembolso for aprovado"` |
| `refund_request.cancelled` | `"o pedido de reembolso for cancelado"` |
| `refund_request.rejected` | `"o reembolso for negado"` |

Editar cada entry no `TRIGGER_EVENTS`, adicionando o campo.

- [ ] **Step 3: TypeScript check**

```bash
cd apps/web && npx tsc --noEmit
```

Esperado: 0 erros.

- [ ] **Step 4: Commit**

```bash
git add apps/web/src/features/onboarding/lib/triggerEvents.ts
git commit -m "feat(onboarding): adiciona triggerVerb aos 25 eventos Hubla"
```

---

### Task 7: Helper `formatRelativeDelay` + testes

**Files:**
- Create: `apps/web/src/features/onboarding/lib/formatRelativeDelay.ts`
- Create: `apps/web/src/features/onboarding/lib/formatRelativeDelay.test.ts`

- [ ] **Step 1: Criar teste falhando**

```ts
// apps/web/src/features/onboarding/lib/formatRelativeDelay.test.ts
import { describe, expect, it } from "vitest";
import { formatRelativeDelay } from "./formatRelativeDelay";

describe("formatRelativeDelay - primeiro step", () => {
  it("0 minutos no 1º step com subscription.activated → 'Assim que a venda for ativada'", () => {
    expect(formatRelativeDelay(0, "subscription.activated", true)).toBe(
      "Assim que a venda for ativada",
    );
  });

  it("120 minutos no 1º step com lead.abandoned_cart → '2 horas após o carrinho for abandonado'", () => {
    expect(formatRelativeDelay(120, "lead.abandoned_cart", true)).toBe(
      "2 horas após o carrinho for abandonado",
    );
  });

  it("evento desconhecido cai em fallback genérico", () => {
    expect(formatRelativeDelay(0, "foo.bar", true)).toBe(
      "Assim que o gatilho disparar",
    );
  });
});

describe("formatRelativeDelay - steps seguintes", () => {
  it("0 minutos no 2º step → 'Junto com a mensagem anterior'", () => {
    expect(formatRelativeDelay(0, "subscription.activated", false)).toBe(
      "Junto com a mensagem anterior",
    );
  });

  it("30 minutos no 2º step → '30 min após a mensagem anterior'", () => {
    expect(formatRelativeDelay(30, "subscription.activated", false)).toBe(
      "30 min após a mensagem anterior",
    );
  });

  it("60 minutos → '1 hora após a mensagem anterior'", () => {
    expect(formatRelativeDelay(60, "subscription.activated", false)).toBe(
      "1 hora após a mensagem anterior",
    );
  });

  it("90 minutos → '1h 30min após a mensagem anterior'", () => {
    expect(formatRelativeDelay(90, "subscription.activated", false)).toBe(
      "1h 30min após a mensagem anterior",
    );
  });

  it("1440 minutos → '1 dia após a mensagem anterior'", () => {
    expect(formatRelativeDelay(1440, "subscription.activated", false)).toBe(
      "1 dia após a mensagem anterior",
    );
  });

  it("2880 minutos → '2 dias após a mensagem anterior'", () => {
    expect(formatRelativeDelay(2880, "subscription.activated", false)).toBe(
      "2 dias após a mensagem anterior",
    );
  });

  it("3030 minutos → '2 dias e 1h 30min após a mensagem anterior'", () => {
    expect(formatRelativeDelay(3030, "subscription.activated", false)).toBe(
      "2 dias e 1h 30min após a mensagem anterior",
    );
  });
});
```

- [ ] **Step 2: Rodar teste e ver falhar**

```bash
cd apps/web && npx vitest run src/features/onboarding/lib/formatRelativeDelay.test.ts 2>&1 | tail -10
```

Esperado: erro de import (módulo não existe).

> Nota: se o projeto não tem `vitest` configurado, pular para Step 4 sem testes automatizados e validar manualmente via consumidores na UI. Verifique: `cat apps/web/package.json | grep -E "vitest|jest|test"`.

- [ ] **Step 3: Implementar `formatRelativeDelay`**

```ts
// apps/web/src/features/onboarding/lib/formatRelativeDelay.ts
import { getTriggerEventMeta } from "./triggerEvents";

/**
 * Gera o texto contextual do badge de delay de um step.
 *
 * Para o 1º step (isFirst=true), usa o `triggerVerb` do evento.
 * Para os demais, fala "após a mensagem anterior".
 *
 * Exemplos:
 *   formatRelativeDelay(0, "subscription.activated", true)
 *     → "Assim que a venda for ativada"
 *   formatRelativeDelay(120, "subscription.activated", true)
 *     → "2 horas após a venda for ativada"
 *   formatRelativeDelay(0, "subscription.activated", false)
 *     → "Junto com a mensagem anterior"
 *   formatRelativeDelay(2880, "subscription.activated", false)
 *     → "2 dias após a mensagem anterior"
 */
export function formatRelativeDelay(
  delayMinutes: number,
  triggerEventType: string,
  isFirst: boolean,
): string {
  const triggerVerb =
    getTriggerEventMeta(triggerEventType)?.triggerVerb ?? "o gatilho disparar";

  if (isFirst) {
    if (delayMinutes === 0) {
      return `Assim que ${triggerVerb}`;
    }
    return `${formatDuration(delayMinutes)} após ${triggerVerb}`;
  }

  if (delayMinutes === 0) {
    return "Junto com a mensagem anterior";
  }
  return `${formatDuration(delayMinutes)} após a mensagem anterior`;
}

/**
 * Formata uma duração em minutos para texto pt-BR.
 *
 *  0     → "Imediato"
 *  1     → "1 min"
 *  30    → "30 min"
 *  60    → "1 hora"
 *  90    → "1h 30min"
 *  1440  → "1 dia"
 *  2880  → "2 dias"
 *  3030  → "2 dias e 1h 30min"
 */
export function formatDuration(minutes: number): string {
  if (minutes === 0) return "Imediato";

  const days = Math.floor(minutes / 1440);
  const remainAfterDays = minutes - days * 1440;
  const hours = Math.floor(remainAfterDays / 60);
  const mins = remainAfterDays - hours * 60;

  const parts: string[] = [];
  if (days > 0) parts.push(days === 1 ? "1 dia" : `${days} dias`);

  // hours+mins agrupados em "Xh Ymin" ou só "X horas" ou só "Y min"
  if (hours > 0 && mins > 0) {
    parts.push(`${hours}h ${mins}min`);
  } else if (hours > 0) {
    parts.push(hours === 1 ? "1 hora" : `${hours} horas`);
  } else if (mins > 0) {
    parts.push(`${mins} min`);
  }

  return parts.join(" e ");
}
```

- [ ] **Step 4: Rodar teste e ver passar (se vitest configurado)**

```bash
cd apps/web && npx vitest run src/features/onboarding/lib/formatRelativeDelay.test.ts 2>&1 | tail -15
```

Esperado: 9 passed.

Se vitest não está configurado, validar via TS check + smoke manual:

```bash
cd apps/web && npx tsc --noEmit
```

- [ ] **Step 5: Commit**

```bash
git add apps/web/src/features/onboarding/lib/formatRelativeDelay.ts \
        apps/web/src/features/onboarding/lib/formatRelativeDelay.test.ts
git commit -m "feat(onboarding): formatRelativeDelay helper + formatDuration"
```

---

## Fase 3 — Frontend componentes

### Task 8: Componente `StepConnector`

**Files:**
- Create: `apps/web/src/features/onboarding/components/StepConnector.tsx`

- [ ] **Step 1: Criar o componente**

```tsx
// apps/web/src/features/onboarding/components/StepConnector.tsx
"use client";

/**
 * Conector visual (linha + chevron) entre cards de step na sequência de mensagens.
 * Renderizado pelo StepList entre cada par de StepItem.
 */
export function StepConnector() {
  return (
    <div
      aria-hidden
      className="flex h-7 items-center justify-center text-outline-variant"
    >
      <svg width="22" height="28" viewBox="0 0 22 28">
        <line
          x1="11"
          y1="2"
          x2="11"
          y2="18"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
        />
        <path
          d="M 5 16 L 11 24 L 17 16"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          fill="none"
        />
      </svg>
    </div>
  );
}
```

- [ ] **Step 2: TypeScript check**

```bash
cd apps/web && npx tsc --noEmit
```

- [ ] **Step 3: Commit**

```bash
git add apps/web/src/features/onboarding/components/StepConnector.tsx
git commit -m "feat(onboarding): StepConnector component (seta SVG entre cards de step)"
```

---

### Task 9: Componente `TimeInputGroup`

**Files:**
- Create: `apps/web/src/features/onboarding/components/TimeInputGroup.tsx`

- [ ] **Step 1: Criar o componente**

```tsx
// apps/web/src/features/onboarding/components/TimeInputGroup.tsx
"use client";

import { useState, useEffect } from "react";

interface TimeInputGroupProps {
  totalMinutes: number;
  onChange: (totalMinutes: number) => void;
  /** Quando false, "Imediato" mostra aviso de "envio junto com a anterior". */
  isFirstStep?: boolean;
}

interface Decomposed {
  days: number;
  hours: number;
  minutes: number;
}

const PRESETS: { label: string; minutes: number }[] = [
  { label: "Imediato", minutes: 0 },
  { label: "15min", minutes: 15 },
  { label: "30min", minutes: 30 },
  { label: "1h", minutes: 60 },
  { label: "2h", minutes: 120 },
  { label: "1 dia", minutes: 1440 },
  { label: "2 dias", minutes: 2880 },
  { label: "3 dias", minutes: 4320 },
  { label: "7 dias", minutes: 10080 },
];

const MAX_DAYS = 365;
const MAX_TOTAL_MINUTES = MAX_DAYS * 24 * 60;

function decompose(totalMinutes: number): Decomposed {
  const safe = Math.max(0, Math.min(MAX_TOTAL_MINUTES, totalMinutes));
  const days = Math.floor(safe / 1440);
  const remainAfterDays = safe - days * 1440;
  const hours = Math.floor(remainAfterDays / 60);
  const minutes = remainAfterDays - hours * 60;
  return { days, hours, minutes };
}

function compose(d: Decomposed): number {
  return d.days * 1440 + d.hours * 60 + d.minutes;
}

export function TimeInputGroup({
  totalMinutes,
  onChange,
  isFirstStep = false,
}: TimeInputGroupProps) {
  const initial = decompose(totalMinutes);
  const [days, setDays] = useState(initial.days);
  const [hours, setHours] = useState(initial.hours);
  const [minutes, setMinutes] = useState(initial.minutes);

  // Sync down se prop externa mudar (auto-fill, edit step)
  useEffect(() => {
    const d = decompose(totalMinutes);
    setDays(d.days);
    setHours(d.hours);
    setMinutes(d.minutes);
  }, [totalMinutes]);

  function emit(d: number, h: number, m: number) {
    const total = compose({ days: d, hours: h, minutes: m });
    onChange(Math.min(MAX_TOTAL_MINUTES, Math.max(0, total)));
  }

  function handleBlur() {
    // Normalização: 90 min → 1h 30min; 30h → 1d 6h
    const total = compose({ days, hours, minutes });
    const normalized = decompose(total);
    setDays(normalized.days);
    setHours(normalized.hours);
    setMinutes(normalized.minutes);
    onChange(total);
  }

  function applyPreset(min: number) {
    const d = decompose(min);
    setDays(d.days);
    setHours(d.hours);
    setMinutes(d.minutes);
    onChange(min);
  }

  const currentTotal = compose({ days, hours, minutes });
  const activePreset = PRESETS.find((p) => p.minutes === currentTotal);
  const showImmediateWarning = currentTotal === 0 && !isFirstStep;

  return (
    <div className="space-y-3">
      <div className="flex items-end gap-2">
        <Spinner
          label="Dias"
          value={days}
          min={0}
          max={MAX_DAYS}
          onChange={(v) => {
            setDays(v);
            emit(v, hours, minutes);
          }}
          onBlur={handleBlur}
        />
        <Spinner
          label="Horas"
          value={hours}
          min={0}
          max={999}
          onChange={(v) => {
            setHours(v);
            emit(days, v, minutes);
          }}
          onBlur={handleBlur}
        />
        <Spinner
          label="Minutos"
          value={minutes}
          min={0}
          max={999}
          onChange={(v) => {
            setMinutes(v);
            emit(days, hours, v);
          }}
          onBlur={handleBlur}
        />
      </div>

      <div className="flex flex-wrap gap-1.5">
        {PRESETS.map((p) => (
          <button
            key={p.label}
            type="button"
            onClick={() => applyPreset(p.minutes)}
            className={`rounded-full border px-3 py-1 text-xs transition-colors ${
              activePreset?.label === p.label
                ? "border-primary/40 bg-primary/10 text-primary"
                : "border-outline-variant bg-surface-container text-on-surface-variant hover:bg-surface-container-high"
            }`}
          >
            {p.label}
          </button>
        ))}
      </div>

      {showImmediateWarning && (
        <p className="text-xs italic text-on-surface-variant">
          Esta mensagem será enviada junto com a anterior.
        </p>
      )}
    </div>
  );
}

interface SpinnerProps {
  label: string;
  value: number;
  min: number;
  max: number;
  onChange: (v: number) => void;
  onBlur: () => void;
}

function Spinner({ label, value, min, max, onChange, onBlur }: SpinnerProps) {
  return (
    <div className="flex flex-col gap-1">
      <span className="text-[10px] font-semibold uppercase tracking-wider text-on-surface-variant">
        {label}
      </span>
      <div className="flex items-center overflow-hidden rounded-lg border border-outline-variant bg-surface">
        <button
          type="button"
          onClick={() => onChange(Math.max(min, value - 1))}
          className="bg-surface-container px-2.5 py-1.5 text-on-surface-variant hover:bg-surface-container-high"
          aria-label={`Diminuir ${label.toLowerCase()}`}
        >
          −
        </button>
        <input
          type="number"
          value={value}
          min={min}
          max={max}
          onChange={(e) => onChange(Math.max(min, Math.min(max, Number(e.target.value) || 0)))}
          onBlur={onBlur}
          className="w-14 border-0 bg-transparent text-center text-sm font-semibold text-on-surface outline-none [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none"
        />
        <button
          type="button"
          onClick={() => onChange(Math.min(max, value + 1))}
          className="bg-surface-container px-2.5 py-1.5 text-on-surface-variant hover:bg-surface-container-high"
          aria-label={`Aumentar ${label.toLowerCase()}`}
        >
          +
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: TypeScript check**

```bash
cd apps/web && npx tsc --noEmit
```

- [ ] **Step 3: Commit**

```bash
git add apps/web/src/features/onboarding/components/TimeInputGroup.tsx
git commit -m "feat(onboarding): TimeInputGroup (3 spinners + chips de preset + auto-normalize)"
```

---

### Task 10: Refatorar `DelayBadge` para usar `formatRelativeDelay`

**Files:**
- Modify: `apps/web/src/features/onboarding/components/DelayBadge.tsx`

- [ ] **Step 1: Ler o estado atual**

```bash
cat /home/fabio/www/agente-plug/apps/web/src/features/onboarding/components/DelayBadge.tsx
```

Identificar a interface de props (provavelmente recebe só `minutes` ou `delay_from_purchase_minutes`).

- [ ] **Step 2: Substituir o conteúdo**

```tsx
// apps/web/src/features/onboarding/components/DelayBadge.tsx
"use client";

import { formatRelativeDelay } from "../lib/formatRelativeDelay";

interface DelayBadgeProps {
  delayMinutes: number;
  triggerEventType: string;
  isFirst: boolean;
}

export function DelayBadge({
  delayMinutes,
  triggerEventType,
  isFirst,
}: DelayBadgeProps) {
  const text = formatRelativeDelay(delayMinutes, triggerEventType, isFirst);
  return (
    <span className="inline-flex items-center rounded-full bg-surface-container-high px-3 py-1 text-xs font-medium text-on-surface-variant">
      {text}
    </span>
  );
}
```

- [ ] **Step 3: TypeScript check**

```bash
cd apps/web && npx tsc --noEmit
```

Se acusar erros em consumidores do `DelayBadge`, eles serão corrigidos na Task 11 (refactor do `StepItem`).

- [ ] **Step 4: Commit**

```bash
git add apps/web/src/features/onboarding/components/DelayBadge.tsx
git commit -m "feat(onboarding): DelayBadge usa formatRelativeDelay (contextual com evento)"
```

---

### Task 11: Refatorar `StepItem` (drag handle persistente + numeração 1+ + props novas do badge)

**Files:**
- Modify: `apps/web/src/features/onboarding/components/StepItem.tsx`

- [ ] **Step 1: Ler o estado atual**

```bash
cat /home/fabio/www/agente-plug/apps/web/src/features/onboarding/components/StepItem.tsx
```

Localizar a linha do drag handle (`group-hover:opacity-100`) e o `DelayBadge`.

- [ ] **Step 2: Mudanças no `StepItem.tsx`**

1. Remover `group-hover:opacity-100` da classe do drag handle. Trocar por `opacity-100` simples (ou apenas remover a regra). O handle continua com `cursor-grab`.

2. Atualizar o uso do `DelayBadge` para passar as 3 props novas:

```tsx
// onde o DelayBadge é renderizado:
<DelayBadge
  delayMinutes={step.delay_from_previous_minutes}
  triggerEventType={triggerEventType}
  isFirst={step.position === 1}
/>
```

3. Adicionar `triggerEventType: string` como nova prop do `StepItem`:

```tsx
interface Props {
  step: OnboardingStep;
  triggerEventType: string;  // ← NOVO
  // ... outros props existentes ...
}
```

4. Trocar uso de `step.delay_from_purchase_minutes` por `step.delay_from_previous_minutes`.

- [ ] **Step 3: Atualizar o tipo `OnboardingStep` no frontend**

```bash
grep -n "delay_from_purchase_minutes" /home/fabio/www/agente-plug/apps/web/src/features/onboarding/types.ts
```

Renomear `delay_from_purchase_minutes` → `delay_from_previous_minutes` em `OnboardingStep`, `CreateStepInput`, `UpdateStepInput`.

- [ ] **Step 4: TypeScript check**

```bash
cd apps/web && npx tsc --noEmit
```

Pode acusar erros em `StepInlineForm` (uso antigo do campo) e em `StepList` (não passa `triggerEventType`). Esses são corrigidos nas Tasks 12 e 13.

- [ ] **Step 5: Commit**

```bash
git add apps/web/src/features/onboarding/components/StepItem.tsx \
        apps/web/src/features/onboarding/types.ts
git commit -m "feat(onboarding): StepItem com drag handle persistente, numeração 1+, label contextual"
```

---

### Task 12: Refatorar `StepInlineForm` (TimeInputGroup + auto-fill)

**Files:**
- Modify: `apps/web/src/features/onboarding/components/StepInlineForm.tsx`

- [ ] **Step 1: Ler o estado atual**

```bash
cat /home/fabio/www/agente-plug/apps/web/src/features/onboarding/components/StepInlineForm.tsx | head -120
```

Identificar:
- Bloco `// Timing` (linhas ~185–211)
- Onde `delay_from_purchase_minutes` aparece nas props `step?: OnboardingStep` e nas chamadas a `onSave`

- [ ] **Step 2: Substituir o bloco de Timing pelo `TimeInputGroup`**

Importar `TimeInputGroup`:

```tsx
import { TimeInputGroup } from "./TimeInputGroup";
```

Adicionar prop `isFirstStep: boolean` e `defaultDelayMinutes: number`:

```tsx
interface Props {
  step?: OnboardingStep;
  nextPosition?: number;
  isFirstStep: boolean;             // ← NOVO
  defaultDelayMinutes: number;      // ← NOVO (vem do StepList para auto-fill)
  onSave: (dto: CreateStepInput | UpdateStepInput) => Promise<void>;
  onCancel: () => void;
}
```

Substituir as funções `minutesToDisplay`/`toMinutes` e o useState `delayValue`/`delayUnit` por:

```tsx
const [totalMinutes, setTotalMinutes] = useState<number>(
  step?.delay_from_previous_minutes ?? defaultDelayMinutes,
);
```

Substituir o JSX do bloco "Timing":

```tsx
{/* Timing */}
<div>
  <label className={labelCls}>
    {isFirstStep
      ? "Tempo de espera após o gatilho"
      : "Tempo de espera após a mensagem anterior"}
  </label>
  <TimeInputGroup
    totalMinutes={totalMinutes}
    onChange={setTotalMinutes}
    isFirstStep={isFirstStep}
  />
</div>
```

E remover o parágrafo de "Imediato — dispara assim que..." (esse texto agora é responsabilidade do `TimeInputGroup` via aviso).

- [ ] **Step 3: Atualizar o submit handler**

Onde o DTO é construído (procurar `onSave({...})`), trocar `delay_from_purchase_minutes` por `delay_from_previous_minutes: totalMinutes`.

- [ ] **Step 4: TypeScript check**

```bash
cd apps/web && npx tsc --noEmit
```

Erros restantes provavelmente vêm do `StepList` (não passa `isFirstStep` nem `defaultDelayMinutes`) — corrigir na Task 13.

- [ ] **Step 5: Commit**

```bash
git add apps/web/src/features/onboarding/components/StepInlineForm.tsx
git commit -m "feat(onboarding): StepInlineForm usa TimeInputGroup + props isFirstStep/defaultDelayMinutes"
```

---

### Task 13: Refatorar `StepList` (estado expandido + auto-open next + conectores + propaga triggerEventType)

**Files:**
- Modify: `apps/web/src/features/onboarding/components/StepList.tsx`
- Modify: `apps/web/src/features/onboarding/components/steps/StepMessageBuilder.tsx` (passar `triggerEventType` down)

- [ ] **Step 1: Atualizar `StepMessageBuilder.tsx` para passar `triggerEventType`**

```tsx
// apps/web/src/features/onboarding/components/steps/StepMessageBuilder.tsx
"use client";

import { StepList } from "../StepList";
import { useOnboardingSteps } from "../../hooks/useOnboardingSteps";

interface StepMessageBuilderProps {
  flowId: string;
  triggerEventType: string;  // ← NOVO
}

export function StepMessageBuilder({
  flowId,
  triggerEventType,
}: StepMessageBuilderProps) {
  const { steps, loading, create, update, remove, reorder } =
    useOnboardingSteps(flowId);

  if (loading) {
    return (
      <div className="text-sm text-on-surface-variant">
        Carregando mensagens...
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div>
        <h3 className="text-sm font-semibold text-on-surface">
          Mensagens da sequência
        </h3>
        <p className="mt-1 text-xs text-on-surface-variant">
          Adicione as mensagens que serão enviadas após o evento gatilho.
          Arraste para reordenar.
        </p>
      </div>
      <StepList
        steps={steps}
        triggerEventType={triggerEventType}
        onCreate={create}
        onUpdate={update}
        onDelete={remove}
        onReorder={reorder}
      />
    </div>
  );
}
```

Confirmar no `FlowDrawer.tsx` que o `<StepMessageBuilder>` recebe `triggerEventType={state.triggerEventType}`:

```bash
grep -n "StepMessageBuilder" /home/fabio/www/agente-plug/apps/web/src/features/onboarding/components/FlowDrawer.tsx
```

Editar a invocação se necessário para incluir a prop.

- [ ] **Step 2: Refatorar `StepList.tsx`**

Adicionar estado `expandedStepId` e `addingAfterStepId`:

```tsx
"use client";

import { useState } from "react";
import {
  DndContext, closestCenter, KeyboardSensor, PointerSensor, useSensor, useSensors,
  type DragEndEvent,
} from "@dnd-kit/core";
import {
  SortableContext, sortableKeyboardCoordinates, verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { useToast } from "@/shared/hooks/useToast";
import { StepItem } from "./StepItem";
import { StepInlineForm } from "./StepInlineForm";
import { StepConnector } from "./StepConnector";
import type {
  CreateStepInput, OnboardingStep, UpdateStepInput,
} from "../types";

interface Props {
  steps: OnboardingStep[];
  triggerEventType: string;          // ← NOVO
  onReorder: (items: { id: string; position: number }[]) => Promise<void>;
  onCreate: (dto: CreateStepInput) => Promise<void>;
  onUpdate: (stepId: string, dto: UpdateStepInput) => Promise<void>;
  onDelete: (stepId: string) => Promise<void>;
}

export function StepList({
  steps, triggerEventType, onReorder, onCreate, onUpdate, onDelete,
}: Props) {
  const toast = useToast();
  const [expandedStepId, setExpandedStepId] = useState<string | null>(null);
  const [addingAfterStepId, setAddingAfterStepId] = useState<string | "start" | null>(null);

  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  async function reorderAndToast(reordered: OnboardingStep[]) {
    try {
      await onReorder(reordered.map((s, i) => ({ id: s.id, position: i + 1 })));
      toast.success("Ordem das mensagens atualizada");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Erro ao reordenar");
    }
  }

  async function handleDragEnd(event: DragEndEvent) {
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    const oldIndex = steps.findIndex((s) => s.id === active.id);
    const newIndex = steps.findIndex((s) => s.id === over.id);
    if (oldIndex < 0 || newIndex < 0) return;
    const reordered = [...steps];
    const [moved] = reordered.splice(oldIndex, 1);
    reordered.splice(newIndex, 0, moved);
    await reorderAndToast(reordered);
  }

  async function handleMoveUp(index: number) {
    if (index === 0) return;
    const reordered = [...steps];
    [reordered[index - 1], reordered[index]] = [reordered[index], reordered[index - 1]];
    await reorderAndToast(reordered);
  }

  async function handleMoveDown(index: number) {
    if (index === steps.length - 1) return;
    const reordered = [...steps];
    [reordered[index], reordered[index + 1]] = [reordered[index + 1], reordered[index]];
    await reorderAndToast(reordered);
  }

  async function handleSaveExisting(
    stepId: string,
    dto: UpdateStepInput,
  ): Promise<void> {
    await onUpdate(stepId, dto);
    const idx = steps.findIndex((s) => s.id === stepId);
    const next = steps[idx + 1];
    if (next) {
      setExpandedStepId(next.id);
    } else {
      setExpandedStepId(null);
      setAddingAfterStepId(stepId);
    }
  }

  async function handleSaveNew(
    dto: CreateStepInput,
  ): Promise<void> {
    await onCreate(dto);
    setAddingAfterStepId(null);
  }

  function defaultDelayFor(positionInList: number): number {
    // Auto-fill: o próximo card vem com o delay do step imediatamente anterior
    if (positionInList === 0) return 0;
    return steps[positionInList - 1]?.delay_from_previous_minutes ?? 0;
  }

  return (
    <div className="flex flex-col">
      <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
        <SortableContext items={steps.map((s) => s.id)} strategy={verticalListSortingStrategy}>
          {steps.map((step, index) => (
            <div key={step.id}>
              {expandedStepId === step.id ? (
                <StepInlineForm
                  step={step}
                  isFirstStep={index === 0}
                  defaultDelayMinutes={step.delay_from_previous_minutes}
                  onSave={async (dto) => {
                    await handleSaveExisting(step.id, dto as UpdateStepInput);
                  }}
                  onCancel={() => setExpandedStepId(null)}
                />
              ) : (
                <StepItem
                  step={step}
                  triggerEventType={triggerEventType}
                  isFirst={index === 0}
                  isLast={index === steps.length - 1}
                  onEdit={() => setExpandedStepId(step.id)}
                  onDelete={() => void onDelete(step.id)}
                  onMoveUp={() => void handleMoveUp(index)}
                  onMoveDown={() => void handleMoveDown(index)}
                />
              )}
              {index < steps.length - 1 && <StepConnector />}
            </div>
          ))}
        </SortableContext>
      </DndContext>

      {/* Adicionar nova mensagem */}
      {addingAfterStepId !== null ? (
        <>
          {steps.length > 0 && <StepConnector />}
          <StepInlineForm
            isFirstStep={steps.length === 0}
            defaultDelayMinutes={defaultDelayFor(steps.length)}
            onSave={async (dto) => {
              await handleSaveNew(dto as CreateStepInput);
            }}
            onCancel={() => setAddingAfterStepId(null)}
          />
        </>
      ) : (
        <button
          type="button"
          onClick={() => setAddingAfterStepId(steps.length === 0 ? "start" : steps[steps.length - 1].id)}
          className="mt-3 inline-flex items-center justify-center gap-2 rounded-lg border border-dashed border-outline-variant px-4 py-3 text-sm text-on-surface-variant hover:border-primary hover:text-primary"
        >
          <span className="material-symbols-outlined" style={{ fontSize: "18px" }}>add</span>
          Adicionar mensagem
        </button>
      )}
    </div>
  );
}
```

> Importante: a assinatura exata de props do `StepItem` pode diferir do que coloquei acima (`isFirst`, `onEdit`, `onMoveUp`, etc). Manter os nomes reais conforme arquivo atual; apenas adicionar `triggerEventType`.

- [ ] **Step 3: TypeScript check**

```bash
cd apps/web && npx tsc --noEmit
```

- [ ] **Step 4: Commit**

```bash
git add apps/web/src/features/onboarding/components/StepList.tsx \
        apps/web/src/features/onboarding/components/steps/StepMessageBuilder.tsx \
        apps/web/src/features/onboarding/components/FlowDrawer.tsx
git commit -m "feat(onboarding): StepList coordena expanded/adding + propaga triggerEventType + conectores SVG"
```

---

## Fase 4 — Validação + cleanup

### Task 14: Validação ponta-a-ponta + lint final

**Files:** (nenhuma modificação — só checks)

- [ ] **Step 1: TypeScript final**

```bash
cd apps/web && npx tsc --noEmit
```

Esperado: 0 erros.

- [ ] **Step 2: Suite api**

```bash
cd apps/api && uv run pytest tests/unit -q 2>&1 | tail -5
```

Esperado: todos passam.

- [ ] **Step 3: Lint**

```bash
cd apps/api && uv run ruff check src tests
cd apps/api && uv run ruff format --check src tests
```

Esperado: All checks passed em ambos.

- [ ] **Step 4: Smoke manual no navegador**

Subir o stack local e validar visualmente:

```bash
docker compose up -d postgres redis
cd apps/api && uv run uvicorn main:app --reload &
cd apps/api && uv run python -m worker &
cd apps/web && npm run dev
```

Em `/onboarding`:

- [ ] Editar um flow existente. Step 3 mostra cards de mensagem com **drag handle visível** sem hover.
- [ ] Numeração começa em **1**.
- [ ] Setas SVG aparecem **entre** os cards.
- [ ] Badge do 1º card: "Assim que [evento]". Badge dos demais: "X após a mensagem anterior".
- [ ] Click em "editar" expande o card com `StepInlineForm`. Campo de tempo mostra 3 inputs (Dias / Horas / Minutos) com botões ± e chips de preset.
- [ ] Clicar em chip "1 dia" preenche os 3 inputs como 1/0/0.
- [ ] Digitar 90 em "Minutos" e clicar fora → vira 1/30 em horas/minutos.
- [ ] Ao salvar um card, ele fecha e o próximo expande automaticamente. Se for o último, o form de "adicionar mensagem" abre embaixo com o tempo do step recém-salvo pré-preenchido.
- [ ] Adicionar mensagem nova → form abre com tempo do último step pré-preenchido (auto-fill).
- [ ] Confirmar visualmente que delay = 0 no card 2+ mostra aviso "envio junto com a anterior".

- [ ] **Step 5: Disparar webhook fake (validação backend do cálculo)**

```bash
curl -X POST http://localhost:8000/webhook/hubla \
  -H "x-hubla-token: $HUBLA_WEBHOOK_SECRET" \
  -H "Content-Type: application/json" \
  -d '{
    "id": "evt_test_relative",
    "type": "subscription.activated",
    "version": "2.0.0",
    "event": {
      "subscription": {
        "id": "sub_test",
        "status": "active",
        "activatedAt": "2026-05-27T00:00:00Z",
        "payer": {
          "firstName": "Teste",
          "lastName": "Cálculo",
          "email": "t@x.com",
          "phone": "+5511999999999"
        },
        "firstPaymentSession": {"utm": {}, "cookies": {}},
        "lastInvoice": {"amount": {}}
      },
      "products": [{"id": "<hubla-product-id-real>", "name": "Teste"}]
    }
  }'
```

Verificar no banco que `scheduled_jobs` criados têm `run_at` cumulativos:

```bash
docker compose exec -T postgres psql -U postgres -d agente_plug -c "
  SELECT run_at, payload->>'enrollment_step_id' AS step_id
  FROM scheduled_jobs
  WHERE kind = 'onboarding_step'
  ORDER BY run_at ASC LIMIT 5;
"
```

Esperado: timestamps acumulando conforme os deltas dos steps.

- [ ] **Step 6: Push e atualizar status do PR (sem abrir ainda — vai junto com Spec B)**

```bash
git push -u origin feat/step-sequence-and-media 2>&1 | tail -3
```

> **Não abrir PR ainda.** A Spec B (mídia em template + webhook na /settings) vai entrar na mesma branch. O PR único é aberto depois que Spec B for implementada também.

---

## Self-Review

### Cobertura da spec

| Spec requirement | Coberto em |
|---|---|
| Setas/conectores SVG entre cards | Task 8 (componente) + Task 13 (uso no StepList) |
| Drag handle sempre visível | Task 11 |
| Numeração começa em 1 | Task 3 (backend) + Task 5 (migration) |
| Label contextual com `triggerVerb` | Task 6 (catalog) + Task 7 (helper) + Task 10 (DelayBadge) + Task 11 (StepItem propaga) |
| 3 inputs Dias/Horas/Minutos + ± + chips + auto-normalize | Task 9 |
| Auto-fill do tempo no próximo card | Task 13 (defaultDelayFor) + Task 12 (StepInlineForm aceita defaultDelayMinutes) |
| Salvar fecha card atual + abre próximo | Task 13 (handleSaveExisting/handleSaveNew + state expandedStepId) |
| Cálculo cumulativo do step anterior | Tasks 1, 2 (backend) + Task 5 (migration) |
| Rename de campo `delay_from_purchase_minutes` → `delay_from_previous_minutes` | Tasks 1, 2, 3, 4, 5, 11, 12 |
| Validações (max 365d, normalize) | Task 3 (Pydantic) + Task 9 (frontend) |
| Aviso "junto com a anterior" em delay=0 card 2+ | Task 9 |

Nenhum gap detectado.

### Pontos resolvidos durante a escrita do plano

- ✅ Constraint de uniqueness em `(flow_id, position)`: confirmado que só existe um índice `ix_onboarding_steps_flow_position` (não-unique), então a migration que aumenta position em 1 não viola unique constraint.
- ✅ Refactor de `enroll_contact` e `resync_enrollment` mapeado nos lugares exatos onde o cálculo absoluto vivia (3 instâncias do timedelta).
- ✅ `StepMessageBuilder` precisa receber `triggerEventType` do `FlowDrawer` — gargalo identificado e endereçado na Task 13 Step 1.

### Pontos que ficam como decisões de implementação razoáveis

- A redação exata de `triggerVerb` por evento pode ser refinada após uso real — a Task 6 documenta a lista inicial proposta. Ajustes pontuais podem entrar em PRs futuros.
- O chip "6h" não foi incluído (presets: Imediato, 15min, 30min, 1h, 2h, 1d, 2d, 3d, 7d). Pode ser adicionado se UX validar a necessidade.
- Vitest pode não estar configurado no projeto — a Task 7 cobre os dois casos (com/sem vitest) para evitar bloqueio na implementação.
