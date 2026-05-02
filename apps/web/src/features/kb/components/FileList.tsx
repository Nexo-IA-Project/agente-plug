// apps/web/src/features/kb/components/FileList.tsx
import { FileItem } from "./FileItem";
import type { KbFile } from "../types";

export function FileList({ files }: { files: KbFile[] }) {
  return (
    <div className="flex w-full flex-col overflow-hidden rounded-xl border border-outline-variant bg-surface-container-low lg:w-80">
      <div className="flex items-center justify-between border-b border-outline-variant bg-surface-container/50 px-4 py-3">
        <span className="text-label-caps font-sans uppercase tracking-wider text-on-surface-variant">
          Arquivos Processados
        </span>
        <span className="rounded bg-surface-container-high px-2 py-0.5 text-xs text-on-surface">
          {files.length}
        </span>
      </div>
      <div className="flex-1 space-y-2 overflow-y-auto p-2">
        {files.map((file) => <FileItem key={file.id} file={file} />)}
      </div>
    </div>
  );
}
