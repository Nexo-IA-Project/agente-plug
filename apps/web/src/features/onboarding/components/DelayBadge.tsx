export function formatDelay(minutes: number): string {
  if (minutes === 0) return "Imediato";
  if (minutes < 60) return `${minutes}min após compra`;
  if (minutes < 1440) {
    const hours = Math.floor(minutes / 60);
    const remainder = minutes % 60;
    return remainder === 0 ? `${hours}h após compra` : `${hours}h ${remainder}min após compra`;
  }
  const days = Math.floor(minutes / 1440);
  const remainder = minutes % 1440;
  if (remainder === 0) return `Dia ${days}`;
  const remHours = Math.floor(remainder / 60);
  const remMins = remainder % 60;
  if (remHours === 0) return `Dia ${days} +${remMins}min`;
  return remMins === 0 ? `Dia ${days} +${remHours}h` : `Dia ${days} +${remHours}h ${remMins}min`;
}

export function DelayBadge({ minutes }: { minutes: number }) {
  return (
    <span className="rounded-full bg-surface-container px-2 py-0.5 text-label-sm text-on-surface-variant font-mono">
      {formatDelay(minutes)}
    </span>
  );
}
