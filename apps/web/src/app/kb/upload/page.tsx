// apps/web/src/app/kb/upload/page.tsx
import { Dropzone } from "@/features/kb/components/Dropzone";
import { FileList } from "@/features/kb/components/FileList";
import { processedFiles } from "@/features/kb/data/kbMocks";

export default function KbUploadPage() {
  return (
    <div className="flex flex-col gap-6 lg:flex-row lg:h-[calc(100vh-128px)]">
      <div className="flex flex-1 flex-col rounded-xl border border-outline-variant bg-surface-container-low p-card-padding">
        <div className="mb-6">
          <h1 className="text-h2 font-sans font-semibold text-on-background">Importação de Conhecimento</h1>
          <p className="mt-1 text-body-sm text-on-surface-variant">
            Arraste e solte arquivos para alimentar a base de conhecimento do agente.
          </p>
        </div>
        <Dropzone />
      </div>
      <FileList files={processedFiles} />
    </div>
  );
}
