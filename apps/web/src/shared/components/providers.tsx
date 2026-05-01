// apps/web/src/shared/components/providers.tsx
"use client";

import { ThemeProvider } from "next-themes";
import { Toaster } from "sonner";

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <ThemeProvider attribute="class" defaultTheme="dark" enableSystem={false} disableTransitionOnChange>
      {children}
      <Toaster
        position="bottom-right"
        toastOptions={{
          classNames: {
            toast:
              "bg-[var(--color-surface-container-high)] border border-[var(--color-outline-variant)] text-[var(--color-on-surface)] font-sans text-sm rounded-lg shadow-none",
            title: "text-[var(--color-on-surface)] font-semibold",
            description: "text-[var(--color-on-surface-variant)]",
            success: "!border-l-4 !border-l-green-500",
            error: "!border-l-4 !border-l-[var(--color-error)]",
            warning: "!border-l-4 !border-l-amber-400",
            info: "!border-l-4 !border-l-[var(--color-secondary)]",
          },
        }}
      />
    </ThemeProvider>
  );
}
