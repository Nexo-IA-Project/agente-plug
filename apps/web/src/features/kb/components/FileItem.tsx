// apps/web/src/features/kb/components/FileItem.tsx
"use client";

import { cn } from "@/lib/utils";
import { useToast } from "@/shared/hooks/useToast";
import type { KbFile } from "../types";

export function FileItem({ file }: { file: KbFile }) {
  const toast = useToast();
  const isError = file.status === "error";

  return (
    <div
      className={cn(
        "relative rounded-lg border p-3 transition-colors",
        isError
          ? "overflow-hidden border-error/30 hover:border-error/50 bg-surface-container"
          : "border-outline-variant bg-surface-container hover:border-outline"
      )}
    >
      {isError && <div className="absolute bottom-0 left-0 top-0 w-1 rounded-l-lg bg-error/50" />}

      <div className={cn("mb-2 flex items-start justify-between", isError && "pl-3")}>
        <div className="flex items-center gap-2 overflow-hidden">
          <span
            className={cn("material-symbols-outlined shrink-0", isError ? "text-error" : "text-on-surface-variant")}
            style={{ fontSize: "18px" }}
          >
            {isError ? "warning" : "description"}
          </span>
          <span className={cn("truncate text-body-sm text-on-surface", isError && "line-through opacity-70")}>
            {file.name}
          </span>
        </div>
        {file.status === "indexed" && (
          <span className="material-symbols-outlined shrink-0 text-primary" style={{ fontSize: "18px" }}>
            check_circle
          </span>
        )}
        {file.status === "processing" && (
          <span className="material-symbols-outlined shrink-0 animate-spin text-on-surface-variant" style={{ fontSize: "18px" }}>
            progress_activity
          </span>
        )}
      </div>

      <div className={cn("flex items-center justify-between", isError && "pl-3")}>
        {isError ? (
          <>
            <span className="text-mono-label font-mono text-error">Erro de leitura</span>
            <button
              onClick={() => toast.info("Tentando novamente...")}
              className="text-on-surface-variant hover:text-on-surface transition-colors"
            >
              <span className="material-symbols-outlined" style={{ fontSize: "16px" }}>refresh</span>
            </button>
          </>
        ) : (
          <>
            <span className="text-mono-label font-mono text-on-surface-variant">{file.size}</span>
            {file.status === "indexed" && (
              <span className="rounded bg-primary/10 px-2 py-0.5 font-mono text-[10px] font-medium uppercase text-primary">
                Indexado
              </span>
            )}
          </>
        )}
      </div>
    </div>
  );
}
