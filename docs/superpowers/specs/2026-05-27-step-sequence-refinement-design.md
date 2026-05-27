# Spec: Refinamento da sequência de mensagens (Onboarding)

**Data:** 2026-05-27
**Status:** Em design — aguardando aprovação do usuário
**Branch alvo:** `feat/step-sequence-and-media` (mesma branch da futura Spec B)
**Spec relacionada (próxima):** Spec B — mídia em template + webhook na /settings (item 6 da demanda original)

---

## Contexto

Após a entrega do stepper de 3 passos (PR #47), o usuário operou a tela em produção e identificou que o **passo 3 (Mensagens)** está com vários atritos de UX:

1. Não há conector visual entre os cards de mensagem — não fica óbvio que é uma sequência ordenada.
2. O label de delay (ex: "Dia 2") é ambíguo — não diz contado a partir do quê.
3. A numeração começa em **0** (bug: `position = len(existing)`).
4. O drag handle só aparece no hover.
5. Ao salvar um card, ele fica aberto — usuário tem que clicar manualmente em "adicionar" pro próximo.
6. O campo de tempo aceita só `valor + unidade` — não permite combinar dias/horas/minutos.
7. O cálculo do delay é **absoluto desde o gatilho** (`delay_from_purchase_minutes`), o que causou confusão real em produção: usuário esperava "esperar 2 dias depois da mensagem anterior" mas o sistema lia "2 dias depois da venda".

Esta spec resolve os 7 atritos numa entrega só. A Spec B (próxima — preview de mídia inline + webhook na /settings) entra na **mesma branch** e abre um PR único.

---

## Objetivos

- **Conectores visuais** entre cards (SVG com linha + chevron apontando pra baixo).
- **Drag handle sempre visível** (remover `group-hover:opacity-100`).
- **Numeração começando em 1** (fix backend + migration corrigindo registros existentes).
- **Label contextual** que usa o nome do evento gatilho do flow:
  - 1º card: "Assim que [evento]" (ex: "Assim que a venda for ativada")
  - 2º+: "X dias e Yh após a mensagem anterior"
- **Campo de tempo** com 3 inputs separados (Dias / Horas / Minutos), botões ± , chips de presets (Imediato, 15min, 30min, 1h, 2h, 1 dia, 2 dias, 3 dias, 7 dias), validações e auto-normalização (90min → 1h 30min ao sair do campo).
- **Auto-fill ao abrir novo card** com os valores de tempo do step anterior (facilita criar sequência iterativa).
- **Salvar fecha card atual + expande o próximo** automaticamente. Se for o último, expande o form de "adicionar mensagem".
- **Cálculo relativo do step anterior** — o delay armazenado é "minutos desde a mensagem anterior", não "minutos desde o gatilho". Isso bate com a expectativa do usuário e o que a UI mostra.

## Não-objetivos

- **Não implementa segundos** — overhead técnico sem caso de uso real.
- **Não mexe no stepper de 3 passos** (Produto / Evento / Mensagens) — só no conteúdo do passo 3.
- **Não muda o sistema de variáveis de template** (`StepVariableBinding`, `VariableResolver`).
- **Não muda a forma de selecionar template Meta** no `StepInlineForm` — isso entra na Spec B (preview de mídia).
- **Não implementa "exibir mídia inline"** no `StepItem` — isso entra na Spec B.

---

## Arquitetura

### Frontend

```
apps/web/src/features/onboarding/
├── components/
│   ├── StepList.tsx              ← passa a coordenar estado expandido + auto-fill
│   ├── StepItem.tsx              ← drag handle sempre visível; numeração 1+
│   ├── StepInlineForm.tsx        ← campo de tempo com 3 inputs + chips de presets
│   ├── StepConnector.tsx         ← NOVO: SVG da seta entre cards
│   ├── DelayBadge.tsx            ← reformulado: usa label contextual
│   └── TimeInputGroup.tsx        ← NOVO: bloco de 3 inputs (Dias/Horas/Min) + spinners + chips
└── lib/
    ├── triggerEvents.ts          ← extender: campo `triggerVerb` ("for ativada", "for abandonado", ...)
    └── formatRelativeDelay.ts    ← NOVO: helper único que monta a string
```

### Backend

```
apps/api/src/
├── shared/
│   ├── adapters/db/models.py
│   │   ├── OnboardingStepModel
│   │   │   delay_from_purchase_minutes → delay_from_previous_minutes
│   │   └── OnboardingEnrollmentStepModel
│   │       delay_from_purchase_minutes → delay_from_previous_minutes (snapshot)
│   ├── application/use_cases/onboarding/
│   │   ├── enroll_contact.py         ← refactor de cálculo (acumula passo a passo)
│   │   ├── resync_enrollment.py      ← mesmo refactor
│   │   └── diff_flow_steps.py        ← rename do campo
│   └── domain/entities/onboarding.py ← rename do campo
├── interface/http/
│   ├── routers/admin/onboarding.py   ← fix `position = len(existing) + 1`
│   └── schemas/onboarding.py         ← Field(ge=1) na position; rename do delay
└── migrations/versions/
    └── <rev>_step_delay_relative_to_previous.py  ← NOVO
```

---

## Detalhamento por item

### 1. Conectores entre cards

**File:** `apps/web/src/features/onboarding/components/StepConnector.tsx` (novo)

```tsx
"use client";

export function StepConnector() {
  return (
    <div className="flex h-7 items-center justify-center">
      <svg width="22" height="28" viewBox="0 0 22 28" aria-hidden>
        <line x1="11" y1="2" x2="11" y2="18"
              stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
        <path d="M 5 16 L 11 24 L 17 16"
              stroke="currentColor" strokeWidth="2"
              strokeLinecap="round" strokeLinejoin="round" fill="none" />
      </svg>
    </div>
  );
}
```

Cor via `text-outline-variant` (tokens NexoIA). Renderizado entre cada par de `StepItem` no `StepList.tsx`.

### 2. Drag handle sempre visível

**File:** `StepItem.tsx`

Remover `group-hover:opacity-100` (linha 88 atual) — o handle aparece com `opacity-100` constante. Para indicar área agarrável, manter `cursor: grab` no hover do próprio handle.

Caractere usado: `⋮⋮` (duas linhas de três pontos verticais), já é o padrão atual. Manter.

### 3. Numeração começa em 1

**Files:**
- `apps/api/src/interface/http/routers/admin/onboarding.py:253`
- `apps/api/src/interface/http/schemas/onboarding.py`
- Migration nova

**Fix do bug:**
```python
# antes
position = body.position if body.position is not None else len(existing)
# depois
position = body.position if body.position is not None else len(existing) + 1
```

**Schema:**
```python
class CreateStepRequest(BaseModel):
    position: int = Field(ge=1)
    # ...
```

**Migration:**
```sql
UPDATE onboarding_steps SET position = position + 1 WHERE id IN (
  SELECT step.id FROM onboarding_steps step
  WHERE NOT EXISTS (
    SELECT 1 FROM onboarding_steps other
    WHERE other.flow_id = step.flow_id AND other.position = step.position + 1
  )
);
-- (versão sentinel-aware da migração — bloco real em Python no upgrade)
```

Idempotência: migration checa se algum step já tem `position = 1` no flow; se sim, pula esse flow.

### 4. Label contextual

**File:** `apps/web/src/features/onboarding/lib/triggerEvents.ts`

Adicionar campo `triggerVerb` à interface `TriggerEventMeta`:

```ts
export interface TriggerEventMeta {
  // ... campos existentes ...
  /**
   * Verbo+substantivo que completa "Assim que a venda for ativada" etc.
   * Usado pelo formatRelativeDelay no 1º card da sequência.
   */
  triggerVerb: string;
}
```

Por evento:
- `subscription.activated` → `"a venda for ativada"`
- `subscription.created` → `"a venda for criada"`
- `subscription.expired` → `"a assinatura expirar"`
- `subscription.deactivated` → `"a assinatura for cancelada"`
- `subscription.auto_renewal_disabled` → `"o cliente desligar a renovação"`
- `subscription.auto_renewal_enabled` → `"o cliente reativar a renovação"`
- `lead.abandoned_cart` → `"o carrinho for abandonado"`
- `member.access_granted` → `"o acesso for concedido"`
- `member.access_removed` → `"o acesso for removido"`
- `invoice.created` → `"a fatura for emitida"`
- `invoice.payment_completed` → `"o pagamento for confirmado"`
- `invoice.payment_failed` → `"o pagamento falhar"`
- (e os outros 13)

**File:** `apps/web/src/features/onboarding/lib/formatRelativeDelay.ts` (novo)

```ts
import { getTriggerEventMeta } from "./triggerEvents";

export function formatRelativeDelay(
  delayMinutes: number,
  triggerEventType: string,
  isFirst: boolean,
): string {
  if (isFirst) {
    const meta = getTriggerEventMeta(triggerEventType);
    return delayMinutes === 0
      ? `Assim que ${meta?.triggerVerb ?? "o gatilho disparar"}`
      : `${formatDuration(delayMinutes)} após ${meta?.triggerVerb ?? "o gatilho"}`;
  }
  return delayMinutes === 0
    ? "Junto com a mensagem anterior"
    : `${formatDuration(delayMinutes)} após a mensagem anterior`;
}

function formatDuration(minutes: number): string {
  // 0 → "Imediato"
  // 30 → "30 min"
  // 60 → "1 hora"
  // 90 → "1h 30min"
  // 1440 → "1 dia"
  // 2880 → "2 dias"
  // 3030 → "2 dias e 25min"
  // ...
}
```

Consumido por `DelayBadge.tsx`.

### 5. Campo de tempo (TimeInputGroup)

**File:** `apps/web/src/features/onboarding/components/TimeInputGroup.tsx` (novo)

```tsx
interface TimeInputGroupProps {
  totalMinutes: number;
  onChange: (totalMinutes: number) => void;
}

export function TimeInputGroup({ totalMinutes, onChange }: TimeInputGroupProps) {
  // Decompõe totalMinutes em { days, hours, minutes }
  // Renderiza 3 spinners (botão ±, input numérico, botão ±)
  // Renderiza chips de presets (Imediato, 15min, 30min, 1h, 2h, 1 dia, 2 dias, 3 dias, 7 dias)
  // Auto-normalização ao blur: se minutes >= 60, transbordar; se hours >= 24, transbordar
  // Setas ↑↓ do teclado funcionam nativamente (input type=number)
}
```

**Validações:**
- Dias: `0–365` (limite duro)
- Horas: `0–23` (auto-overflow ao 24+ → +1 dia)
- Minutos: `0–59` (auto-overflow ao 60+ → +1 hora)
- Total mínimo absoluto: 0 (Imediato)
- Total máximo absoluto: 365 dias

**Avisos não-bloqueantes:**
- Se `totalMinutes === 0` no card 2+, mostrar abaixo: *"Esta mensagem será enviada junto com a anterior."* (em itálico, cinza, não bloqueia o submit).

**Presets (chips):**
- "Imediato" (0min)
- "15min" / "30min"
- "1h" / "2h"
- "1 dia" / "2 dias" / "3 dias" / "7 dias"

Clicar em chip preenche os 3 inputs. Chip ativo fica destacado quando os 3 valores batem com algum preset.

### 6. Auto-fill ao abrir novo card

**File:** `StepList.tsx`

Quando o usuário clica "Adicionar mensagem":
1. Se há ao menos 1 step existente, o form abre com `totalMinutes = lastStep.delayFromPreviousMinutes` (não com 0).
2. Template e variáveis ficam vazios (cada mensagem é independente).

Quando o usuário salva um step e o `StepList` automaticamente expande o próximo (item 7 abaixo):
- Se o próximo já existe → expande pra editar
- Se não existe → abre o form de adicionar, pré-populando `totalMinutes` com o valor do step recém-salvo

### 7. Salvar fecha card atual + abre próximo

**File:** `StepList.tsx`

Estado novo:
```tsx
const [expandedStepId, setExpandedStepId] = useState<string | null>(null);
const [isAddingAfter, setIsAddingAfter] = useState<string | null>(null);
```

Fluxo:
- `handleSave(stepId)`:
  1. Chama `onUpdate(stepId, dto)` ou `onCreate(dto)` no backend
  2. Em sucesso:
     - Encontra próximo step na ordem
     - Se existe → `setExpandedStepId(nextStepId)`
     - Se não existe → `setIsAddingAfter(stepId)` (abre form de adicionar)
- `handleCancel()`: `setExpandedStepId(null); setIsAddingAfter(null);`

**Comportamento de "Concluir" no step 3 do drawer maior** permanece igual (fecha drawer).

### 8. Cálculo relativo (backend)

**Files:**
- `apps/api/src/shared/adapters/db/models.py`
- `apps/api/src/shared/domain/entities/onboarding.py`
- `apps/api/src/shared/application/use_cases/onboarding/enroll_contact.py`
- `apps/api/src/shared/application/use_cases/onboarding/resync_enrollment.py`
- `apps/api/src/shared/application/use_cases/onboarding/diff_flow_steps.py`
- `apps/api/src/interface/http/schemas/onboarding.py`

**Renomeação:**
- `delay_from_purchase_minutes` → `delay_from_previous_minutes`
- Aplicar em `OnboardingStepModel`, `OnboardingEnrollmentStepModel`, entities, schemas (DTOs `CreateStepRequest`, `UpdateStepRequest`, `StepResponse`), nomes correspondentes no frontend (`CreateStepInput`, `UpdateStepInput`, `OnboardingStep`).

**Refactor de cálculo (`enroll_contact.py`):**

```python
# antes (cada step calcula absoluto desde purchase_time)
for step in flow_steps:
    run_at = purchase_time + timedelta(minutes=step.delay_from_purchase_minutes)
    # ...

# depois (cada step calcula relativo do anterior, mantendo um cursor)
base_time = purchase_time
for step in sorted(flow_steps, key=lambda s: s.position):
    base_time = base_time + timedelta(minutes=step.delay_from_previous_minutes)
    run_at = base_time
    # ...
```

Mesmo padrão em `resync_enrollment.py` (duas instâncias do cálculo).

### Migration

**File:** `apps/api/migrations/versions/<rev>_step_delay_relative_to_previous.py`

```python
def upgrade() -> None:
    # 1. Adiciona coluna nova com default 0
    op.add_column(
        "onboarding_steps",
        sa.Column("delay_from_previous_minutes", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "onboarding_enrollment_steps",
        sa.Column("delay_from_previous_minutes", sa.Integer(), nullable=False, server_default="0"),
    )

    # 2. Converte valores existentes
    conn = op.get_bind()
    for table in ("onboarding_steps", "onboarding_enrollment_steps"):
        rows = conn.execute(sa.text(f"""
            SELECT id, flow_id, position, delay_from_purchase_minutes
            FROM {table}
            ORDER BY flow_id, position
        """)).fetchall()
        prev_by_flow: dict = {}
        for r in rows:
            prev = prev_by_flow.get(r.flow_id, 0)
            relative = max(0, r.delay_from_purchase_minutes - prev)
            conn.execute(
                sa.text(f"UPDATE {table} SET delay_from_previous_minutes = :rel WHERE id = :id"),
                {"rel": relative, "id": r.id},
            )
            prev_by_flow[r.flow_id] = r.delay_from_purchase_minutes

    # 3. Corrige position zero-indexed em flows legacy
    conn.execute(sa.text("""
        UPDATE onboarding_steps SET position = position + 1
        WHERE flow_id IN (
            SELECT DISTINCT flow_id FROM onboarding_steps
            WHERE position = 0
        )
    """))
    conn.execute(sa.text("""
        UPDATE onboarding_enrollment_steps SET position = position + 1
        WHERE enrollment_id IN (
            SELECT DISTINCT enrollment_id FROM onboarding_enrollment_steps
            WHERE position = 0
        )
    """))

    # 4. Dropa coluna antiga (mantemos esse passo opcional caso queira validação manual antes)
    op.drop_column("onboarding_steps", "delay_from_purchase_minutes")
    op.drop_column("onboarding_enrollment_steps", "delay_from_purchase_minutes")


def downgrade() -> None:
    # 1. Recria coluna antiga
    op.add_column(
        "onboarding_steps",
        sa.Column("delay_from_purchase_minutes", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "onboarding_enrollment_steps",
        sa.Column("delay_from_purchase_minutes", sa.Integer(), nullable=False, server_default="0"),
    )

    # 2. Reconstrói absoluto via soma cumulativa
    conn = op.get_bind()
    for table in ("onboarding_steps", "onboarding_enrollment_steps"):
        rows = conn.execute(sa.text(f"""
            SELECT id, flow_id, position, delay_from_previous_minutes
            FROM {table}
            ORDER BY flow_id, position
        """)).fetchall()
        cumulative_by_flow: dict = {}
        for r in rows:
            cum = cumulative_by_flow.get(r.flow_id, 0) + r.delay_from_previous_minutes
            conn.execute(
                sa.text(f"UPDATE {table} SET delay_from_purchase_minutes = :abs WHERE id = :id"),
                {"abs": cum, "id": r.id},
            )
            cumulative_by_flow[r.flow_id] = cum

    # 3. Reverte position (1-indexed → 0-indexed)
    conn.execute(sa.text("""
        UPDATE onboarding_steps SET position = position - 1 WHERE position > 0
    """))
    conn.execute(sa.text("""
        UPDATE onboarding_enrollment_steps SET position = position - 1 WHERE position > 0
    """))

    op.drop_column("onboarding_steps", "delay_from_previous_minutes")
    op.drop_column("onboarding_enrollment_steps", "delay_from_previous_minutes")
```

**Garantia de equivalência semântica:**
Para qualquer flow existente, soma cumulativa após upgrade = absoluto antes do upgrade. Logo, scheduled_at recalculado pelo `resync_enrollment` futuro produz os mesmos timestamps. Não há mudança de comportamento para flows pré-existentes — só pra fluxos novos com a nova semântica.

---

## Data flow

### Fluxo de criação de step (UI)

```
1. Usuário clica "Adicionar mensagem"
   → StepList abre form pré-preenchido com totalMinutes do step anterior (ou 0 se 1º)
2. Usuário ajusta tempo (Dias/Horas/Min ou chip de preset)
3. Usuário escolhe template Meta + variáveis (sem mudança)
4. Usuário clica "Salvar"
   → POST /admin/onboarding/flows/{id}/steps com { position, delay_from_previous_minutes, template_name, ... }
   → Backend retorna step criado
   → StepList fecha o form atual, expande o próximo (ou abre form de adicionar se for o último)
```

### Fluxo de enrollment (backend)

```
Hubla manda evento → HublaEventHandler.handle()
  → produto resolvido → flows encontrados
  → para cada flow → EnrollContact.execute()
    → base_time = purchase_time (ou enrollment_at)
    → para cada step em ordem de position:
        base_time = base_time + timedelta(minutes=step.delay_from_previous_minutes)
        run_at = base_time
        → scheduler.create_job(run_at=run_at, kind="onboarding_step", payload={...})
```

---

## Error handling

- **Migration idempotente:** se rodar 2x, o segundo `UPDATE position = position + 1` é gated por `WHERE position = 0`. Conversão de delay também: na segunda execução, `delay_from_purchase_minutes` já foi dropada → falha cedo com erro de coluna. Documentar em comentário.
- **Frontend valida limites no input** (não permite digitar > 23 em horas, > 59 em minutos), mas **backend valida também** via `Field(ge=0, le=365*24*60)` em `CreateStepRequest`.
- **Auto-fill conservador:** se usuário começou a digitar campos manualmente após o auto-fill, preserva o que ele digitou (não sobrescreve).
- **"Junto com a anterior"** (delay = 0 em card 2+): permitido com aviso visual; não bloqueia submit. Isso permite "enviar 3 mensagens ao mesmo tempo" se for desejado.

---

## Testes

- **`formatRelativeDelay` unit:** matriz de minutos × eventType × isFirst → verifica labels esperadas.
- **`TimeInputGroup` smoke:** simular digitação 90 minutos → blur → verifica que vira 1h 30min.
- **`enroll_contact.execute` integration:** flow com 3 steps (delays 0, 120, 60 min) → assert run_at = T+0, T+2h, T+3h.
- **Migration test:** seed 1 flow com 3 steps (absolutos: 0, 2880, 4320) → upgrade → assert delay_from_previous_minutes = (0, 2880, 1440). Downgrade → assert volta a (0, 2880, 4320).
- **Smoke test manual** (após implementar): criar flow novo via UI, completar 3 cards com tempos, validar que badge mostra texto correto.

---

## Riscos

| Risco | Severidade | Mitigação |
|---|---|---|
| Migration converte tempos errado em flows com `position` não-sequencial | Média | Migration ordena por `(flow_id, position)` e processa linearmente. Mas se houver gaps (1, 3, 5 sem 2, 4), continua coerente — diff usa step anterior na ordem real do banco. |
| Flows ativos em prod recebem migration durante deploy → janela curta com schemas inconsistentes | Baixa | Migration roda antes do deploy do código novo (CI/CD em ordem). Coluna nova é populada antes de remover a antiga. |
| Usuário não percebe que auto-fill veio do step anterior | Baixa | Visualmente o campo já está preenchido com valor != 0; placeholder não aparece. Se confundir, é fácil sobrescrever. |
| Chips de preset cobrem mal um caso comum (ex: 6h) | Baixa | Adicionar quick-pick "6h" se a UX validar demanda. Por ora os 9 chips cobrem ~95% dos casos. |
| `triggerVerb` para 18 eventos é redação subjetiva | Baixa | Versões iniciais podem ser refinadas após uso. Define um padrão "for [verbo]" / "o cliente [verbo]" pra consistência. |

---

## Critérios de aceite

- [ ] StepList renderiza seta SVG entre cada par de cards
- [ ] Drag handle `⋮⋮` visível em 100% do tempo (não só hover)
- [ ] Primeiro card de qualquer flow novo tem `position = 1` (sem 0)
- [ ] Flows pré-existentes têm `position` migrado pra começar em 1
- [ ] Badge do 1º card mostra "Assim que a venda for ativada" (varia conforme trigger)
- [ ] Badge do 2º+ mostra "X dias e Yh após a mensagem anterior"
- [ ] Campo tempo com 3 inputs separados, botões ± funcionais, setas teclado funcionais
- [ ] Auto-normalização: digitar 90 em minutos vira 1h 30min ao sair do campo
- [ ] Chips de preset preenchem os 3 inputs corretamente
- [ ] Ao abrir novo card via "Adicionar", tempo já vem pré-preenchido com valores do step anterior
- [ ] Ao salvar um card, ele fecha e o próximo expande (ou form de adicionar abre)
- [ ] `enroll_contact` agenda 3 steps com run_at = T+delay1, T+delay1+delay2, T+delay1+delay2+delay3
- [ ] `resync_enrollment` segue mesmo cálculo
- [ ] Migration upgrade roda sem erro; valores convertidos batem
- [ ] Migration downgrade reverte (smoke test)
- [ ] Aviso "junto com a anterior" aparece se delay = 0 em card 2+

---

## Plano de plan-time (próximos passos após aprovação)

1. Confirmar lista de `triggerVerb` por evento Hubla (revisar redação dos 25).
2. Decidir se chip "6h" deve entrar (opcional).
3. Definir lista exata de chips de preset (atual: 9 chips).
4. Após implementar e mergear, brainstormar a **Spec B** (mídia em template + webhook na /settings) na **mesma branch**.

Tasks detalhadas vão no plano de implementação (próximo skill: `writing-plans`).
