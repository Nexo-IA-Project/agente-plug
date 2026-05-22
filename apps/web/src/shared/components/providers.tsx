// apps/web/src/shared/components/providers.tsx
"use client";

import { ThemeProvider } from "next-themes";
import { Toaster } from "sonner";
import { ConfirmProvider } from "./confirm/ConfirmProvider";

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <ThemeProvider attribute="class" defaultTheme="dark" enableSystem={false} disableTransitionOnChange>
      <ConfirmProvider>{children}</ConfirmProvider>
      <Toaster
        position="top-center"
        richColors={false}
        closeButton
        gap={12}
        offset={24}
        toastOptions={{
          duration: 4000,
          unstyled: false,
          classNames: {
            toast: [
              "nx-toast group/toast pointer-events-auto",
              "flex items-start gap-3.5",
              // QUADRADO — sem border-radius
              "rounded-none border-0 border-l-[4px]",
              // MAIOR — padding + tipografia + largura mínima
              "px-5 py-4 text-[15px] tracking-tight",
              "min-w-[360px] max-w-[440px]",
              // Sombra firme — peso de bloco
              "shadow-[0_10px_28px_rgba(0,0,0,0.45),0_2px_6px_rgba(0,0,0,0.3)]",
              // Variants — saturados, não pastel. Texto branco em todos.
              "data-[type=success]:!bg-emerald-600 data-[type=success]:!border-l-emerald-300 data-[type=success]:!text-white",
              "data-[type=error]:!bg-rose-600 data-[type=error]:!border-l-rose-300 data-[type=error]:!text-white",
              "data-[type=warning]:!bg-amber-500 data-[type=warning]:!border-l-amber-200 data-[type=warning]:!text-white",
              "data-[type=info]:!bg-sky-600 data-[type=info]:!border-l-sky-300 data-[type=info]:!text-white",
              // Default (sem type) — surface do tema
              "data-[type]:bg-surface-container-high data-[type]:border-l-outline-variant",
            ].join(" "),
            title: [
              "font-semibold leading-snug text-white",
              "group-data-[type=success]/toast:!text-white",
              "group-data-[type=error]/toast:!text-white",
              "group-data-[type=warning]/toast:!text-white",
              "group-data-[type=info]/toast:!text-white",
            ].join(" "),
            description: [
              "mt-1 text-[13px] leading-relaxed text-white/85",
              "group-data-[type=success]/toast:!text-white/85",
              "group-data-[type=error]/toast:!text-white/85",
              "group-data-[type=warning]/toast:!text-white/90",
              "group-data-[type=info]/toast:!text-white/85",
            ].join(" "),
            icon: [
              "shrink-0 mt-0.5 [&_svg]:size-5",
              "text-white",
              "group-data-[type=success]/toast:!text-white",
              "group-data-[type=error]/toast:!text-white",
              "group-data-[type=warning]/toast:!text-white",
              "group-data-[type=info]/toast:!text-white",
            ].join(" "),
            closeButton: [
              // Estilo do botão — posicionamento controlado via globals.css
              "!rounded-none !border-0 !bg-transparent !text-white/80 hover:!text-white hover:!bg-white/15",
            ].join(" "),
          },
        }}
      />
    </ThemeProvider>
  );
}
