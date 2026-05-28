"use client";

/**
 * Loading overlay full-screen — usado em operações longas (save de template,
 * sync de mídia, etc). Fundo quase invisível pra não bloquear visualmente,
 * com ícone destacado no centro.
 */
interface LoadingOverlayProps {
  open: boolean;
  /** Texto opcional abaixo do ícone (ex: "Salvando template..."). */
  label?: string;
  /** Material Symbols icon name. Default: progress_activity (spinner). */
  icon?: string;
}

export function LoadingOverlay({
  open,
  label,
  icon = "progress_activity",
}: LoadingOverlayProps) {
  return (
    <div
      role="status"
      aria-live="polite"
      aria-hidden={!open}
      className={`pointer-events-${open ? "auto" : "none"} fixed inset-0 z-[60] flex items-center justify-center transition-opacity duration-200`}
      style={{
        opacity: open ? 1 : 0,
        backgroundColor: "rgba(255,255,255,0.08)",
        backdropFilter: open ? "blur(2px)" : "none",
      }}
    >
      <div
        className="flex flex-col items-center gap-3 rounded-2xl bg-surface-container px-8 py-7 shadow-2xl"
        style={{
          boxShadow:
            "0 24px 80px rgba(0,0,0,0.18), 0 4px 16px rgba(0,0,0,0.10)",
          transform: open ? "scale(1)" : "scale(0.92)",
          transition:
            "transform 320ms cubic-bezier(0.16, 1, 0.3, 1), opacity 200ms ease",
        }}
      >
        <div className="relative">
          {/* Halo sutil */}
          <div
            aria-hidden
            className="absolute inset-0 animate-pulse rounded-full bg-primary/20 blur-2xl"
            style={{ animationDuration: "1800ms" }}
          />
          <span
            className="material-symbols-outlined relative animate-spin text-primary"
            style={{
              fontSize: "44px",
              fontVariationSettings: "'FILL' 1, 'GRAD' 200",
              animationDuration: "1200ms",
            }}
          >
            {icon}
          </span>
        </div>
        {label && (
          <p className="max-w-[260px] text-center text-sm font-medium text-on-surface">
            {label}
          </p>
        )}
      </div>
    </div>
  );
}
