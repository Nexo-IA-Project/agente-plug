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
