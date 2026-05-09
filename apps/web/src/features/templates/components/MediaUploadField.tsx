"use client";

import { useCallback, useRef, useState } from "react";
import { uploadTemplateMedia } from "@/lib/api";
import { useToast } from "@/shared/hooks/useToast";
import { MEDIA_LIMITS, validateMediaFile } from "../validation";
import type { MediaKind, UploadedMedia } from "../types";

interface Props {
  kind: MediaKind;
  value: UploadedMedia | null;
  onChange: (media: UploadedMedia | null) => void;
}

const KIND_LABEL: Record<MediaKind, string> = {
  IMAGE: "Imagem",
  VIDEO: "Vídeo",
  DOCUMENT: "Documento",
};

const KIND_ICON: Record<MediaKind, string> = {
  IMAGE: "image",
  VIDEO: "videocam",
  DOCUMENT: "description",
};

function formatBytes(b: number): string {
  if (b < 1024) return `${b} B`;
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`;
  return `${(b / 1024 / 1024).toFixed(1)} MB`;
}

export function MediaUploadField({ kind, value, onChange }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [progress, setProgress] = useState<number | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const toast = useToast();
  const limits = MEDIA_LIMITS[kind];
  const maxMb = limits.maxBytes / (1024 * 1024);

  const handleFiles = useCallback(
    async (files: FileList | null) => {
      const file = files?.[0];
      if (!file) return;
      const err = validateMediaFile(file, kind);
      if (err) {
        toast.error(err.message);
        return;
      }
      try {
        setProgress(0);
        const out = await uploadTemplateMedia(file, kind, setProgress);
        onChange({
          url: out.media_url,
          objectKey: out.media_object_key,
          kind: out.media_kind,
          size: out.size,
          sha256: out.sha256,
          fileName: file.name,
        });
        toast.success("Mídia enviada com sucesso");
      } catch (e) {
        toast.error(`Falha no upload: ${e instanceof Error ? e.message : String(e)}`);
      } finally {
        setProgress(null);
      }
    },
    [kind, onChange, toast],
  );

  if (value) {
    return (
      <div className="rounded-lg border border-outline-variant bg-surface-container p-3 flex items-center gap-3">
        <span className="material-symbols-outlined text-on-surface-variant">
          {KIND_ICON[kind]}
        </span>
        <div className="flex-1 min-w-0">
          <div className="text-sm font-medium text-on-surface truncate">{value.fileName}</div>
          <div className="text-xs text-on-surface-variant">
            {KIND_LABEL[kind]} · {formatBytes(value.size)}
          </div>
        </div>
        <button
          type="button"
          className="text-sm text-primary hover:underline"
          onClick={() => inputRef.current?.click()}
        >
          Trocar
        </button>
        <button
          type="button"
          className="text-sm text-error hover:underline"
          onClick={() => onChange(null)}
        >
          Remover
        </button>
        <input
          ref={inputRef}
          type="file"
          accept={limits.mimes.join(",")}
          className="hidden"
          onChange={(e) => handleFiles(e.target.files)}
        />
      </div>
    );
  }

  return (
    <div
      className={`rounded-lg border-2 border-dashed p-6 text-center cursor-pointer transition ${
        dragOver
          ? "border-primary bg-primary/5"
          : "border-outline-variant bg-surface-container hover:border-primary"
      }`}
      onClick={() => inputRef.current?.click()}
      onDragOver={(e) => {
        e.preventDefault();
        setDragOver(true);
      }}
      onDragLeave={() => setDragOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragOver(false);
        handleFiles(e.dataTransfer.files);
      }}
    >
      {progress !== null ? (
        <div className="space-y-2">
          <div className="text-sm text-on-surface">Enviando {progress}%…</div>
          <div className="h-2 bg-outline-variant rounded overflow-hidden">
            <div
              className="h-full bg-primary transition-all"
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>
      ) : (
        <>
          <span className="material-symbols-outlined text-4xl text-on-surface-variant">
            cloud_upload
          </span>
          <div className="text-sm text-on-surface mt-1">
            Arraste {KIND_LABEL[kind].toLowerCase()} aqui ou{" "}
            <span className="text-primary">clique pra selecionar</span>
          </div>
          <div className="text-xs text-on-surface-variant mt-1">
            Max {maxMb}MB · {limits.mimes.map((m) => m.split("/")[1]).join(", ")}
          </div>
        </>
      )}
      <input
        ref={inputRef}
        type="file"
        accept={limits.mimes.join(",")}
        className="hidden"
        onChange={(e) => handleFiles(e.target.files)}
      />
    </div>
  );
}
