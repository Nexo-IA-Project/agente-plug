"use client";

import { useRouter } from "next/navigation";
import { ThemeToggle } from "./ThemeToggle";
import { clearToken } from "@/lib/auth";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export function TopBar() {
  const router = useRouter();

  async function handleLogout() {
    // Limpa localStorage + cookie não-HttpOnly
    clearToken();
    // Pede ao servidor para deletar o cookie HttpOnly (JS não consegue fazer isso)
    await fetch(`${API_URL}/admin/auth/logout`, {
      method: "POST",
      credentials: "include",
    }).catch(() => {});
    router.push("/login");
  }

  return (
    <header className="sticky top-0 z-40 flex h-16 items-center justify-between border-b border-outline-variant bg-surface/80 backdrop-blur-md px-8">
      <div className="relative flex max-w-sm flex-1 items-center">
        <span className="material-symbols-outlined absolute left-3 text-on-surface-variant" style={{ fontSize: "18px" }}>
          search
        </span>
        <input
          type="text"
          placeholder="Buscar..."
          aria-label="Buscar"
          className="w-full rounded-lg border border-outline-variant bg-surface-container py-2 pl-10 pr-4 text-body-sm text-on-surface placeholder:text-on-surface-variant outline-none focus:ring-2 focus:ring-primary transition-all"
        />
      </div>

      <div className="flex items-center gap-2">
        <button aria-label="Notificações" className="relative flex h-9 w-9 items-center justify-center rounded-lg text-on-surface-variant hover:bg-surface-container hover:text-on-surface transition-colors">
          <span className="material-symbols-outlined" style={{ fontSize: "20px" }}>notifications</span>
          <span className="absolute right-1.5 top-1.5 h-2 w-2 rounded-full bg-primary" />
        </button>
        <button aria-label="Ajuda" className="flex h-9 w-9 items-center justify-center rounded-lg text-on-surface-variant hover:bg-surface-container hover:text-on-surface transition-colors">
          <span className="material-symbols-outlined" style={{ fontSize: "20px" }}>help_outline</span>
        </button>
        <ThemeToggle />
        <div className="ml-2 flex h-8 w-8 items-center justify-center rounded-full bg-primary text-on-primary text-xs font-semibold select-none">
          FD
        </div>
        <button
          onClick={handleLogout}
          aria-label="Sair"
          className="flex h-9 w-9 items-center justify-center rounded-lg text-on-surface-variant hover:bg-error/10 hover:text-error transition-colors"
        >
          <span className="material-symbols-outlined" style={{ fontSize: "20px" }}>logout</span>
        </button>
      </div>
    </header>
  );
}
