# Spec: Refinamento visual do FlowDrawer + preview de template no celular

**Data:** 2026-05-27
**Status:** Em design — aprovado via mockups
**Branch alvo:** `feat/step-sequence-and-media` (mesma branch dos PRs anteriores — PR #49 em aberto)

---

## Contexto

Após validação visual em produção do FlowDrawer (passo 3 implementado nas Specs A+B), 5 ajustes de UI/UX foram solicitados:

1. **Conectores entre cards são cor de fundo** — quase invisíveis. Aumentar contraste.
2. **Rail lateral atual parece "stepper indicator"** — quer estilo sidebar real (com label + hint visível por step, background sutil, borda).
3. **Editar flow existente abre no step 1** — preferia abrir direto no step 3 (Mensagens), que é o estado típico de edição.
4. **Painel de conteúdo confunde com fundo do drawer** — quer fundo branco no conteúdo + padding + borda separando sidebar e conteúdo.
5. **Não há preview visual do template** em `/templates` — quer botão "Visualizar" abrindo modal com dispositivo iPhone renderizando a mensagem WhatsApp completa (efeito scale-from-center do modal de criação).

---

## Objetivos

### 1. Setas mais nítidas (`StepConnector`)
- Trocar cor do SVG de `text-outline-variant` para `text-on-surface-variant`
- Garantir contraste visível em fundos light + dark

### 2. Sidebar real no `FlowDrawer`
- Largura **260px** fixa
- Background `bg-surface-container-low` (vs branco do conteúdo)
- Borda divisória `border-r border-outline-variant`
- Cada step listado com: círculo numerado (28px) + label + hint (produto/evento/contagem mensagens)
- Estado visual: `current` (pill colorida), `done` (verde + check), `pending`/`locked` (cinza)
- Cabeçalho da sidebar: subtítulo "Configurando flow" + título dinâmico ("Novo fluxo" / "Editar fluxo")

### 3. Editar abre no step 3
- `useEffect` que hidrata o `StepperState` ao abrir o drawer: quando `flow !== null`, setar `current: 3` (em vez de `current: 1`)
- Novo flow continua abrindo em step 1
- Rail clicável livre para voltar aos steps 1/2 conforme já implementado

### 4. Fundo branco no conteúdo do drawer
- Container do conteúdo (à direita da sidebar): `bg-surface` (branco no light)
- Padding interno: `px-8 py-7` (≈ 32×28)
- Sem mudar o fundo geral do drawer (continua `bg-surface-container`)

### 5. Preview de template no iPhone
- Botão **Visualizar** (ícone `visibility`) em cada `TemplateCard` na `/templates` — posicionado próximo aos botões existentes (Editar/Excluir)
- Componente novo: `TemplatePreviewModal` em `apps/web/src/features/templates/components/`
  - Modal central com mesma transição do `TemplateModal` de criação (scale 0.78 → 1, opacity 0 → 1, cubic-bezier(0.16, 1, 0.3, 1), 600ms)
  - Header do modal: nome do template + pills de categoria/idioma/status
  - Corpo: componente `IPhonePreview` (novo) renderizando bolha WhatsApp dentro de moldura de iPhone
  - Footer: botão "Fechar"
- Componente `IPhonePreview` (`apps/web/src/features/templates/components/IPhonePreview.tsx`):
  - Moldura preta `rounded-[38px]` + notch + tela `#ece5dd` (background WhatsApp)
  - Header verde WhatsApp `#075e54` com avatar + nome "Cliente"
  - Bolha verde `#dcf8c6` com:
    - Mídia (img/video/document) se header tem `media_url`
    - Header de texto (bold) se header é TEXT
    - Body com variáveis `{{var}}` destacadas em cinza
    - Footer (italic, fonte menor)
    - Botões (cada um em pill)
    - Timestamp + check duplo
  - Largura ~280px, altura ~540px

---

## Não-objetivos

- Não mudar a estrutura de 3 passos (Produto / Evento / Mensagens) — só o visual da sidebar.
- Não mudar fluxo de animação **entre steps** do FlowDrawer (slide+fade existentes mantidos).
- Não criar `IPhonePreview` reutilizado no `StepInlineForm` — o `TemplatePreview` atual (bolha inline simples) permanece lá. O iPhone só aparece em `/templates`.
- Não implementar editar template via novo modal — botão Visualizar é só leitura.

---

## Arquitetura

### Frontend

```
apps/web/src/features/
├── onboarding/
│   └── components/
│       ├── FlowDrawer.tsx          ← sidebar layout + fundo branco + abrir step 3 ao editar
│       └── StepConnector.tsx       ← cor mais nítida
└── templates/
    ├── components/
    │   ├── TemplateList.tsx        ← botão Visualizar em cada card
    │   ├── TemplatePreviewModal.tsx  ← NOVO: modal scale-from-center
    │   └── IPhonePreview.tsx       ← NOVO: moldura iPhone + bolha WhatsApp
    └── ...
```

---

## Detalhamento por item

### Item 1 — Setas mais nítidas

**File:** `apps/web/src/features/onboarding/components/StepConnector.tsx`

```tsx
<div
  aria-hidden
  className="flex h-7 items-center justify-center text-on-surface-variant"  // ← era text-outline-variant
>
```

Resto do SVG idêntico.

### Item 2 — Sidebar real + Item 3 — Editar abre step 3 + Item 4 — Fundo branco

**File:** `apps/web/src/features/onboarding/components/FlowDrawer.tsx`

Mudanças:

1. **Hidratação inicial (item 3):** no `useEffect` que ajusta state ao abrir:
   ```tsx
   if (flow) {
     setState({
       current: 3,  // ← era 1
       direction: "forward",
       productId: flow.product.id,
       triggerEventType: (flow.trigger_event_type as HublaEventType) ?? "subscription.activated",
       isActive: flow.is_active,
       flowId: flow.id,
     });
   }
   ```

2. **Sidebar (item 2) + fundo (item 4):** substituir o rail vertical fininho por uma sidebar coluna:
   ```tsx
   <div className="flex h-full">
     {/* Sidebar */}
     <aside className="w-[260px] shrink-0 border-r border-outline-variant bg-surface-container-low px-4 py-6">
       <div className="mb-5 px-3">
         <p className="text-[10px] font-semibold uppercase tracking-wider text-on-surface-variant">
           Configurando flow
         </p>
         <p className="mt-1 text-sm font-semibold text-on-surface">
           {isEditing ? "Editar fluxo" : "Novo fluxo de onboarding"}
         </p>
       </div>
       <SidebarSteps
         steps={stepDescriptors}
         onNavigate={(idx) => { if (canNavigateTo(idx)) goTo(idx); }}
       />
     </aside>

     {/* Conteúdo (fundo branco) */}
     <div className="min-w-0 flex-1 overflow-auto bg-surface px-8 py-7">
       <div
         key={state.current}
         className={state.direction === "forward" ? "onboarding-step-forward" : "onboarding-step-backward"}
       >
         {/* StepProductPicker / StepEventPicker / StepMessageBuilder iguais */}
       </div>
     </div>
   </div>
   ```

3. **Novo componente `SidebarSteps`** (substitui `StepRail` no `FlowDrawer`):

   Cada step é uma linha clicável com:
   - Círculo numerado 28px (estados: current=primary, done=emerald, pending/locked=outline-variant)
   - Label
   - Hint (sub-texto cinza)
   - `aria-current="step"` quando atual

   Pode ser definido localmente no `FlowDrawer.tsx` ou em `steps/StepSidebarItem.tsx`. Optar pelo local pra reduzir churn.

   > **Decisão:** componente `SidebarSteps` fica inline no `FlowDrawer.tsx` (~30 linhas). Não vale criar arquivo separado por enquanto.

4. **Remover** o uso atual do `StepRail`. Manter o arquivo `StepRail.tsx` exportado (caso outras telas dependam) — verificar:
   ```bash
   grep -rn "StepRail" apps/web/src/
   ```
   Se só `FlowDrawer` usa, deletar `StepRail.tsx` na limpeza.

### Item 5 — Preview de template no iPhone

#### 5a. Componente `IPhonePreview`

**File:** `apps/web/src/features/templates/components/IPhonePreview.tsx`

Recebe `template: MetaTemplate` e renderiza:

```tsx
"use client";

import type { MetaTemplate } from "../types";

interface Props {
  template: MetaTemplate;
}

export function IPhonePreview({ template }: Props) {
  const header = template.components.find((c) => c.type === "HEADER");
  const body = template.components.find((c) => c.type === "BODY");
  const footer = template.components.find((c) => c.type === "FOOTER");
  const buttons = template.components.find((c) => c.type === "BUTTONS")?.buttons ?? [];

  const showImage = header?.format === "IMAGE" && template.media_url;
  const showVideo = header?.format === "VIDEO" && template.media_url;
  const showDoc = header?.format === "DOCUMENT" && template.media_url;
  const showTextHeader = header?.format === "TEXT" && header.text;

  return (
    <div className="relative mx-auto w-[280px] rounded-[38px] bg-black p-2 shadow-2xl">
      <div className="absolute left-1/2 top-2 z-10 h-6 w-[120px] -translate-x-1/2 rounded-b-2xl bg-black" />
      <div className="flex h-[540px] flex-col overflow-hidden rounded-[30px] bg-[#ece5dd]">
        {/* WhatsApp Header */}
        <div className="flex items-center gap-3 bg-[#075e54] pb-2 pl-3 pr-3 pt-8 text-white">
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-emerald-400">
            <span className="text-sm">👤</span>
          </div>
          <div className="flex-1">
            <p className="text-[13px] font-semibold leading-tight">Cliente</p>
            <p className="text-[10px] opacity-80">online</p>
          </div>
          <div className="flex gap-3 text-sm opacity-80">
            <span>📞</span>
            <span>⋮</span>
          </div>
        </div>

        {/* Chat area */}
        <div className="flex-1 overflow-y-auto p-3">
          <div className="max-w-[86%] rounded-lg rounded-bl-none bg-[#dcf8c6] p-2.5 shadow-sm">
            {showImage && (
              <img
                src={template.media_url!}
                alt=""
                className="mb-1.5 h-[130px] w-full rounded object-cover"
              />
            )}
            {showVideo && (
              <video
                src={template.media_url!}
                controls
                className="mb-1.5 h-[130px] w-full rounded bg-black"
              />
            )}
            {showDoc && (
              <a
                href={template.media_url!}
                target="_blank"
                rel="noopener noreferrer"
                className="mb-1.5 flex items-center gap-1.5 rounded border border-zinc-300 bg-white px-2 py-1.5 text-[11px] text-zinc-800"
              >
                <span className="material-symbols-outlined text-sm">description</span>
                <span className="truncate">{template.name}</span>
              </a>
            )}
            {showTextHeader && (
              <p className="mb-1.5 text-[12px] font-semibold">{header.text}</p>
            )}
            {body?.text && (
              <p className="whitespace-pre-wrap text-[12px] leading-snug">
                {renderWithVariables(body.text)}
              </p>
            )}
            {footer?.text && (
              <p className="mt-1.5 text-[10px] italic text-zinc-500">{footer.text}</p>
            )}
            <p className="mt-1 text-right text-[9px] text-zinc-500">14:23 ✓✓</p>
          </div>
          {buttons.length > 0 && (
            <div className="ml-0 mt-1 flex flex-col gap-0.5">
              {buttons.map((btn, i) => (
                <div
                  key={i}
                  className="rounded border border-zinc-300 bg-white py-1.5 text-center text-[11px] font-medium text-sky-700"
                >
                  {btn.text ?? "Botão"}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function renderWithVariables(text: string): React.ReactNode {
  // Renderiza {{var}} com destaque visual (badge cinza)
  const parts: React.ReactNode[] = [];
  const regex = /\{\{([^}]+)\}\}/g;
  let lastIdx = 0;
  let match: RegExpExecArray | null;
  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIdx) parts.push(text.slice(lastIdx, match.index));
    parts.push(
      <span
        key={match.index}
        className="rounded bg-zinc-200 px-1 py-0.5 text-[10px] font-mono text-zinc-700"
      >
        {`{{${match[1]}}}`}
      </span>,
    );
    lastIdx = regex.lastIndex;
  }
  if (lastIdx < text.length) parts.push(text.slice(lastIdx));
  return parts;
}
```

#### 5b. Componente `TemplatePreviewModal`

**File:** `apps/web/src/features/templates/components/TemplatePreviewModal.tsx`

```tsx
"use client";

import { useEffect, useState } from "react";
import type { MetaTemplate } from "../types";
import { IPhonePreview } from "./IPhonePreview";

interface Props {
  template: MetaTemplate | null;
  onClose: () => void;
}

export function TemplatePreviewModal({ template, onClose }: Props) {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    if (!template) {
      setVisible(false);
      return;
    }
    const raf = requestAnimationFrame(() => setVisible(true));
    return () => cancelAnimationFrame(raf);
  }, [template]);

  function handleClose() {
    setVisible(false);
    setTimeout(onClose, 320);
  }

  useEffect(() => {
    if (!template) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") handleClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [template]);  // eslint-disable-line react-hooks/exhaustive-deps

  if (!template) return null;

  return (
    <div
      className="fixed z-40"
      style={{
        left: "240px",
        right: 0,
        top: 0,
        bottom: 0,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      <div
        className="absolute inset-0 bg-scrim/60"
        style={{ opacity: visible ? 1 : 0, transition: "opacity 500ms ease" }}
        onClick={handleClose}
      />
      <div
        className="relative z-50 flex flex-col bg-surface-container p-6"
        style={{
          width: "min(480px, calc(100% - 64px))",
          maxHeight: "90vh",
          borderRadius: "20px",
          boxShadow: "0 24px 80px rgba(0,0,0,0.5), 0 4px 16px rgba(0,0,0,0.3)",
          transformOrigin: "center center",
          transform: visible ? "scale(1)" : "scale(0.78)",
          opacity: visible ? 1 : 0,
          transition: "transform 600ms cubic-bezier(0.16, 1, 0.3, 1), opacity 480ms ease",
          overflow: "hidden",
        }}
      >
        <button
          onClick={handleClose}
          className="absolute right-3 top-3 rounded-lg p-1.5 text-on-surface-variant hover:bg-surface-container-high"
          aria-label="Fechar"
        >
          <span className="material-symbols-outlined" style={{ fontSize: "20px" }}>close</span>
        </button>

        <div className="mb-4 text-center">
          <h3 className="text-base font-semibold text-on-surface">{template.name}</h3>
          <p className="mt-0.5 text-xs text-on-surface-variant font-mono">
            {template.category} · {template.language}
          </p>
          <div className="mt-2 inline-flex gap-1.5">
            <span className="rounded-full bg-primary/10 px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-primary">
              {template.status?.toLowerCase()}
            </span>
          </div>
        </div>

        <IPhonePreview template={template} />

        <div className="mt-5 flex justify-center">
          <button
            type="button"
            onClick={handleClose}
            className="rounded-lg bg-primary px-6 py-2.5 text-sm font-medium text-on-primary hover:bg-primary/90"
          >
            Fechar
          </button>
        </div>
      </div>
    </div>
  );
}
```

#### 5c. Botão "Visualizar" no `TemplateList`

Adicionar ao lado dos botões existentes em cada card:

```tsx
<button
  type="button"
  onClick={() => onPreview?.(t)}
  title="Visualizar"
  className="flex h-10 w-10 items-center justify-center rounded-xl text-on-surface-variant hover:bg-primary/10 hover:text-primary"
>
  <span className="material-symbols-outlined">visibility</span>
</button>
```

Props nova: `onPreview?: (template: MetaTemplate) => void`.

#### 5d. State + integração na page `/templates`

`apps/web/src/app/(admin)/templates/page.tsx`:

```tsx
const [previewing, setPreviewing] = useState<MetaTemplate | null>(null);

// no JSX:
<TemplateList
  // ... outras props ...
  onPreview={setPreviewing}
/>
<TemplatePreviewModal template={previewing} onClose={() => setPreviewing(null)} />
```

---

## Critérios de aceite

- [ ] `StepConnector` renderiza com `text-on-surface-variant` (mais escuro/nítido)
- [ ] Ao abrir flow existente, drawer abre direto no step 3
- [ ] Sidebar 260px à esquerda no FlowDrawer, com label + hint por step
- [ ] Conteúdo da direita tem fundo branco (`bg-surface`), padding 28×32, borda dividindo da sidebar
- [ ] Botão `visibility` aparece em cada `TemplateCard` em `/templates`
- [ ] Clicar abre `TemplatePreviewModal` com efeito scale-from-center
- [ ] Modal mostra nome + categoria/idioma + pill de status no header
- [ ] iPhone renderizado com notch + bordas + tela WhatsApp completa
- [ ] Variáveis `{{var}}` aparecem com destaque visual no preview
- [ ] Mídia (IMAGE/VIDEO/DOCUMENT) renderiza no preview quando template tem mídia
- [ ] Botões do template aparecem como pills clicáveis (apenas visual, não funcional)
- [ ] ESC + click no backdrop fecham o modal
- [ ] TS 0 erros + tests passam

---

## Riscos

| Risco | Severidade | Mitigação |
|---|---|---|
| iPhone preview pode ficar visualmente "pobre" em comparação ao polum-app | Baixa | Mockup já validado; tokens NexoIA na implementação real ficam consistentes. |
| Edit abrindo step 3 pode confundir usuário que quer recadastrar produto | Baixa | Rail sidebar continua clicável; voltar a step 1/2 é 1 clique. |
| Largura 260px da sidebar pode espremer conteúdo em telas estreitas | Baixa | Drawer ocupa quase a tela toda; 260px de 1200px é razoável. |
| Botão "Visualizar" mais um ícone no card pode poluir a UI | Baixa | Mesmo padrão dos botões Editar/Excluir; cabe sem refactor. |
