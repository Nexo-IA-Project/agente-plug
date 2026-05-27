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
