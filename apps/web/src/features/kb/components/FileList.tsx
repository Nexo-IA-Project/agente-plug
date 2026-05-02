// apps/web/src/features/kb/components/FileList.tsx
"use client";

import { useState } from "react";
import { FileItem } from "./FileItem";
import type { KbFile } from "../types";

export function FileList({ files }: { files: KbFile[] }) {
  const [search, setSearch] = useState("");
  const filtered = files.filter((f) =>
    f.name.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="flex w-full flex-col overflow-hidden rounded-xl border border-outline-variant bg-surface-container-low lg:w-80">
      <div className="flex items-center justify-between border-b border-outline-variant px-4 py-3">
        <span className="text-body-sm font-semibold text-on-surface">Arquivos na Base</span>
        <span className="rounded-full bg-surface-container-high px-2.5 py-0.5 text-xs font-medium text-on-surface-variant">
          {files.length} Arquivos
        </span>
      </div>

      <div className="border-b border-outline-variant px-3 py-2">
        <div className="relative">
          <span
            className="material-symbols-outlined absolute left-2.5 top-1/2 -translate-y-1/2 text-on-surface-variant"
            style={{ fontSize: "16px" }}
          >
            search
          </span>
          <input
            type="text"
            placeholder="Filtrar arquivos..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full rounded-lg border border-outline-variant bg-surface-container py-2 pl-8 pr-3 text-body-sm text-on-surface placeholder:text-on-surface-variant outline-none focus:ring-2 focus:ring-primary transition-all"
          />
        </div>
      </div>

      <div className="flex-1 space-y-2 overflow-y-auto p-2">
        {filtered.length > 0 ? (
          filtered.map((file) => <FileItem key={file.id} file={file} />)
        ) : (
          <p className="py-6 text-center text-body-sm text-on-surface-variant">Nenhum arquivo encontrado.</p>
        )}
      </div>
    </div>
  );
}
