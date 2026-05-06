// apps/web/src/app/kb/page.tsx
import { Dropzone } from "@/features/kb/components/Dropzone";
import { FileList } from "@/features/kb/components/FileList";
import { processedFiles } from "@/features/kb/data/kbMocks";

export default function KbPage() {
  return (
    <div className="flex h-[calc(100vh-128px)] flex-col gap-6 lg:flex-row">
      <div className="flex flex-1 flex-col rounded-xl border border-outline-variant bg-surface-container-low p-card-padding">
        <div className="mb-6">
          <h1 className="text-h1 font-bold text-on-surface">Adicionar Arquivos</h1>
          <p className="mt-1 text-body-sm text-on-surface-variant">
            Carregue documentos para treinar sua IA. Formatos suportados: PDF, DOCX, TXT.
          </p>
        </div>
        <Dropzone />
      </div>
      <FileList files={processedFiles} />
    </div>
  );
}
