// apps/web/src/app/kb/page.tsx
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { DocumentTable } from "@/components/kb/document-table";
import { listDocuments } from "@/lib/api";
import type { KbDocument } from "@/types/api";
import { Upload } from "lucide-react";

// The account_id will come from session/auth in a future iteration.
// For now, read from env or default to "1" for development.
const ACCOUNT_ID = process.env.DEFAULT_ACCOUNT_ID ?? "1";

export default async function KbListPage() {
  let documents: KbDocument[] = [];
  let error: string | null = null;

  try {
    const response = await listDocuments(ACCOUNT_ID);
    documents = response.items;
  } catch (err) {
    error = err instanceof Error ? err.message : "Erro ao carregar documentos.";
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">
            Base de Conhecimento
          </h1>
          <p className="text-muted-foreground">
            Gerencie os documentos que o agente usa para responder dúvidas.
          </p>
        </div>
        <Button asChild>
          <Link href="/kb/upload">
            <Upload className="mr-2 h-4 w-4" />
            Upload
          </Link>
        </Button>
      </div>

      {error ? (
        <div className="rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {error}
        </div>
      ) : (
        <DocumentTable documents={documents} />
      )}
    </div>
  );
}
