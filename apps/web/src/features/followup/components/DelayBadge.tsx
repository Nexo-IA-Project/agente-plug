export function formatDelay(hours: number): string {
  if (hours === 0) return "Imediato";
  if (hours < 24) return `${hours}h após compra`;
  const days = Math.floor(hours / 24);
  const rem = hours % 24;
  return rem === 0 ? `Dia ${days}` : `Dia ${days} +${rem}h`;
}

export function DelayBadge({ hours }: { hours: number }) {
  return (
    <span className="rounded-full bg-surface-container px-2 py-0.5 text-label-sm text-on-surface-variant font-mono">
      {formatDelay(hours)}
    </span>
  );
}
