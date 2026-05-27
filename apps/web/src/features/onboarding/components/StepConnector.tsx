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
