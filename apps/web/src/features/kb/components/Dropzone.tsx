// apps/web/src/features/kb/components/Dropzone.tsx
"use client";

import { useState, useCallback } from "react";
import { useToast } from "@/shared/hooks/useToast";
import { UploadProgress } from "./UploadProgress";

const ACCEPTED = [".pdf", ".docx", ".txt"];

export function Dropzone() {
  const toast = useToast();
  const [isDragOver, setIsDragOver] = useState(false);
  const [uploadingFile, setUploadingFile] = useState<{ name: string; progress: number } | null>(null);

  const processFile = useCallback(
    (file: File) => {
      const ext = file.name.toLowerCase().slice(file.name.lastIndexOf("."));
      if (!ACCEPTED.includes(ext)) {
        toast.error("Formato não suportado", `Use: ${ACCEPTED.join(", ")}`);
        return;
      }
      toast.success("Arquivo enviado para processamento", file.name);
      setUploadingFile({ name: file.name, progress: 45 });
      setTimeout(() => setUploadingFile(null), 2000);
    },
    [toast]
  );

  return (
    <div className="flex flex-1 flex-col">
      <div
        onDragOver={(e) => { e.preventDefault(); setIsDragOver(true); }}
        onDragLeave={(e) => {
          if (e.currentTarget.contains(e.relatedTarget as Node)) return;
          setIsDragOver(false);
        }}
        onDrop={(e) => { e.preventDefault(); setIsDragOver(false); const f = e.dataTransfer.files[0]; if (f) processFile(f); }}
        className={`relative flex flex-1 min-h-[280px] flex-col items-center justify-center rounded-xl border-2 border-dashed transition-colors ${
          isDragOver ? "border-primary bg-primary/5" : "border-outline-variant hover:border-outline"
        }`}
      >
        <input
          type="file"
          accept={ACCEPTED.join(",")}
          onChange={(e) => { const f = e.target.files?.[0]; if (f) processFile(f); }}
          className="absolute inset-0 z-10 h-full w-full cursor-pointer opacity-0"
        />
        <div className="pointer-events-none flex flex-col items-center px-8 text-center">
          <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-surface-container-high">
            <span className="material-symbols-outlined text-on-surface-variant" style={{ fontSize: "28px" }}>
              cloud_upload
            </span>
          </div>
          <h3 className="text-body-base font-semibold text-on-surface">Arraste um arquivo aqui</h3>
          <p className="mt-1 text-body-sm text-on-surface-variant">ou clique para selecionar do seu computador</p>
          <div className="mt-6 flex gap-3">
            {ACCEPTED.map((fmt) => (
              <span key={fmt} className="rounded-full border border-outline-variant bg-surface-container-high px-3 py-1 font-mono text-mono-label uppercase text-on-surface-variant">
                {fmt.replace(".", "")}
              </span>
            ))}
          </div>
        </div>
      </div>

      {uploadingFile && <UploadProgress filename={uploadingFile.name} progress={uploadingFile.progress} />}
    </div>
  );
}
