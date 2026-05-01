// apps/web/src/app/kb/upload/page.tsx
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { UploadForm } from "@/components/kb/upload-form";
import { ArrowLeft } from "lucide-react";

const ACCOUNT_ID = process.env.DEFAULT_ACCOUNT_ID ?? "1";

export default function KbUploadPage() {
  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="sm" asChild>
          <Link href="/kb">
            <ArrowLeft className="mr-1 h-4 w-4" />
            Voltar
          </Link>
        </Button>
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Upload de documento</h1>
          <p className="text-muted-foreground">
            Adicione um novo documento à base de conhecimento.
          </p>
        </div>
      </div>

      <UploadForm accountId={ACCOUNT_ID} />
    </div>
  );
}
