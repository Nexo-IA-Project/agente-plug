// apps/web/src/components/kb/upload-form.tsx
"use client";

import { useState, useRef } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { uploadDocument } from "@/lib/api";
import { Upload, FileText, CheckCircle2 } from "lucide-react";

interface UploadFormProps {
  accountId: string;
}

export function UploadForm({ accountId }: UploadFormProps) {
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const selected = e.target.files?.[0] ?? null;
    setFile(selected);
    setError(null);
    setSuccess(false);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!file) {
      setError("Selecione um arquivo para fazer o upload.");
      return;
    }

    const allowed = [".pdf", ".docx", ".txt"];
    const ext = file.name.toLowerCase().slice(file.name.lastIndexOf("."));
    if (!allowed.includes(ext)) {
      setError(`Formato não suportado. Use: ${allowed.join(", ")}`);
      return;
    }

    setUploading(true);
    setError(null);

    try {
      await uploadDocument(accountId, file);
      setSuccess(true);
      setFile(null);
      if (fileInputRef.current) fileInputRef.current.value = "";
      setTimeout(() => router.push("/kb"), 1500);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro no upload.");
    } finally {
      setUploading(false);
    }
  }

  return (
    <Card className="max-w-lg">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base font-semibold">
          <Upload className="h-4 w-4" />
          Novo documento
        </CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <label
              htmlFor="file-input"
              className="text-sm font-medium leading-none"
            >
              Arquivo (PDF, DOCX ou TXT)
            </label>
            <Input
              id="file-input"
              ref={fileInputRef}
              type="file"
              accept=".pdf,.docx,.txt"
              onChange={handleFileChange}
              disabled={uploading}
            />
          </div>

          {file && (
            <div className="flex items-center gap-2 rounded-md bg-muted p-3 text-sm">
              <FileText className="h-4 w-4 text-muted-foreground" />
              <span className="truncate">{file.name}</span>
              <span className="ml-auto text-xs text-muted-foreground">
                {(file.size / 1024).toFixed(1)} KB
              </span>
            </div>
          )}

          {error && (
            <p className="text-sm text-red-600">{error}</p>
          )}

          {success && (
            <div className="flex items-center gap-2 text-sm text-green-700">
              <CheckCircle2 className="h-4 w-4" />
              Upload realizado! Redirecionando...
            </div>
          )}

          <Button type="submit" disabled={uploading || !file} className="w-full">
            {uploading ? "Enviando..." : "Fazer upload"}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
