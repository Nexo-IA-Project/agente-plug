// apps/web/src/features/kb/components/UploadProgress.tsx
export function UploadProgress({ filename, progress }: { filename: string; progress: number }) {
  return (
    <div className="mt-4 rounded-lg border border-outline-variant bg-surface-container p-4">
      <div className="mb-2 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="material-symbols-outlined text-primary" style={{ fontSize: "20px" }}>description</span>
          <span className="text-body-sm font-medium text-on-surface">{filename}</span>
        </div>
        <span className="text-mono-label font-mono text-on-surface-variant">{progress}%</span>
      </div>
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-surface-container-highest">
        <div className="h-full rounded-full bg-primary transition-all duration-300" style={{ width: `${progress}%` }} />
      </div>
    </div>
  );
}
