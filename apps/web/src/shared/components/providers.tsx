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
        gap={10}
        offset={20}
        toastOptions={{
          duration: 3500,
          unstyled: false,
          classNames: {
            toast: [
              "group/toast pointer-events-auto",
              "flex items-start gap-3",
              "rounded-2xl border px-4 py-3.5 text-sm",
              "shadow-[0_8px_32px_rgba(0,0,0,0.35),0_2px_8px_rgba(0,0,0,0.25)]",
              "backdrop-blur-md",
              // Success — verde claro / texto verde escuro
              "data-[type=success]:!bg-green-100 data-[type=success]:!border-green-300",
              "data-[type=success]:!border-l-[4px] data-[type=success]:!border-l-green-600",
              // Error — vermelho claro / texto vermelho escuro
              "data-[type=error]:!bg-red-100 data-[type=error]:!border-red-300",
              "data-[type=error]:!border-l-[4px] data-[type=error]:!border-l-red-600",
              // Warning — âmbar claro / texto âmbar escuro
              "data-[type=warning]:!bg-amber-100 data-[type=warning]:!border-amber-300",
              "data-[type=warning]:!border-l-[4px] data-[type=warning]:!border-l-amber-600",
              // Info — azul claro / texto azul escuro
              "data-[type=info]:!bg-blue-100 data-[type=info]:!border-blue-300",
              "data-[type=info]:!border-l-[4px] data-[type=info]:!border-l-blue-600",
              // Default (sem type) — surface do tema
              "data-[type]:bg-surface-container-high data-[type]:border-outline-variant/40",
            ].join(" "),
            title: [
              "font-semibold leading-snug",
              "group-data-[type=success]/toast:!text-green-900",
              "group-data-[type=error]/toast:!text-red-900",
              "group-data-[type=warning]/toast:!text-amber-900",
              "group-data-[type=info]/toast:!text-blue-900",
            ].join(" "),
            description: [
              "mt-0.5 text-xs leading-relaxed",
              "group-data-[type=success]/toast:!text-green-800",
              "group-data-[type=error]/toast:!text-red-800",
              "group-data-[type=warning]/toast:!text-amber-800",
              "group-data-[type=info]/toast:!text-blue-800",
            ].join(" "),
            icon: [
              "shrink-0 mt-0.5",
              "group-data-[type=success]/toast:!text-green-700",
              "group-data-[type=error]/toast:!text-red-700",
              "group-data-[type=warning]/toast:!text-amber-700",
              "group-data-[type=info]/toast:!text-blue-700",
            ].join(" "),
            closeButton: [
              "!border-current/30",
              "group-data-[type=success]/toast:!bg-green-200 group-data-[type=success]/toast:!text-green-900 group-data-[type=success]/toast:hover:!bg-green-300",
              "group-data-[type=error]/toast:!bg-red-200 group-data-[type=error]/toast:!text-red-900 group-data-[type=error]/toast:hover:!bg-red-300",
              "group-data-[type=warning]/toast:!bg-amber-200 group-data-[type=warning]/toast:!text-amber-900 group-data-[type=warning]/toast:hover:!bg-amber-300",
              "group-data-[type=info]/toast:!bg-blue-200 group-data-[type=info]/toast:!text-blue-900 group-data-[type=info]/toast:hover:!bg-blue-300",
            ].join(" "),
          },
        }}
      />
    </ThemeProvider>
  );
}
