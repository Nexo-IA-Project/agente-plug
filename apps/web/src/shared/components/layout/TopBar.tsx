// apps/web/src/shared/components/layout/TopBar.tsx
import { ThemeToggle } from "./ThemeToggle";

export function TopBar() {
  return (
    <header className="sticky top-0 z-40 flex h-16 items-center justify-between border-b border-outline-variant bg-surface/80 backdrop-blur-md px-8">
      <div className="relative flex max-w-sm flex-1 items-center">
        <span className="material-symbols-outlined absolute left-3 text-on-surface-variant" style={{ fontSize: "18px" }}>
          search
        </span>
        <input
          type="text"
          placeholder="Buscar..."
          className="w-full rounded-lg border border-outline-variant bg-surface-container py-2 pl-10 pr-4 text-body-sm text-on-surface placeholder:text-on-surface-variant outline-none focus:ring-2 focus:ring-primary transition-all"
        />
      </div>

      <div className="flex items-center gap-2">
        <button className="relative flex h-9 w-9 items-center justify-center rounded-lg text-on-surface-variant hover:bg-surface-container hover:text-on-surface transition-colors">
          <span className="material-symbols-outlined" style={{ fontSize: "20px" }}>notifications</span>
          <span className="absolute right-1.5 top-1.5 h-2 w-2 rounded-full bg-primary" />
        </button>
        <button className="flex h-9 w-9 items-center justify-center rounded-lg text-on-surface-variant hover:bg-surface-container hover:text-on-surface transition-colors">
          <span className="material-symbols-outlined" style={{ fontSize: "20px" }}>help_outline</span>
        </button>
        <ThemeToggle />
        <div className="ml-2 flex h-8 w-8 items-center justify-center rounded-full border border-outline-variant bg-surface-container">
          <span className="material-symbols-outlined text-on-surface-variant" style={{ fontSize: "16px" }}>person</span>
        </div>
      </div>
    </header>
  );
}
