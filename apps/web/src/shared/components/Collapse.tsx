"use client";

import { useEffect, useState } from "react";

/**
 * Anima a altura real do conteúdo (qualquer altura) entre 0 e auto, junto com
 * opacity. Usa o truque `grid-template-rows: 0fr → 1fr` que permite a transição
 * de height sem precisar de max-height hardcoded.
 *
 * Por que `display: grid`: a row implícita tem `fr`-value, e fr-values podem
 * ser animadas pelo browser entre estados — algo que `height: auto` não permite.
 *
 * Uso:
 *   <Collapse open={mode === "template"}>
 *     <ConteudoComAlturaVariavel />
 *   </Collapse>
 */
interface Props {
  open: boolean;
  children: React.ReactNode;
  /** Duração em ms — default 420 (mesma família das outras transições do app) */
  durationMs?: number;
  /** Easing — default cubic-bezier(0.22, 1, 0.36, 1) (mesma do toast/step) */
  easing?: string;
  /** Anima também no mount inicial (útil quando o componente é montado já com open=true) */
  animateOnMount?: boolean;
  /** Classe adicional aplicada no wrapper */
  className?: string;
}

export function Collapse({
  open,
  children,
  durationMs = 420,
  easing = "cubic-bezier(0.22, 1, 0.36, 1)",
  animateOnMount = true,
  className,
}: Props) {
  // Quando animateOnMount, começa fechado no mount mesmo se open=true, e abre
  // logo após o paint via requestAnimationFrame. Isso garante que a transição
  // CSS seja disparada (browsers não animam mudanças aplicadas no mesmo frame).
  const [mounted, setMounted] = useState(!animateOnMount);

  useEffect(() => {
    if (animateOnMount && !mounted) {
      const raf = requestAnimationFrame(() => setMounted(true));
      return () => cancelAnimationFrame(raf);
    }
    return undefined;
  }, [animateOnMount, mounted]);

  const expanded = mounted && open;

  return (
    <div
      className={["grid", className].filter(Boolean).join(" ")}
      style={{
        gridTemplateRows: expanded ? "1fr" : "0fr",
        opacity: expanded ? 1 : 0,
        transition: `grid-template-rows ${durationMs}ms ${easing}, opacity ${durationMs}ms ${easing}`,
      }}
    >
      <div className="overflow-hidden">{children}</div>
    </div>
  );
}
