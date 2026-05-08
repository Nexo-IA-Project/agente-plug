// apps/web/src/components/kb/document-table.tsx
"use client";

import { useState } from "react";
import Link from "next/link";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Trash2 } from "lucide-react";
import { deleteDocument } from "@/lib/api";
import { useConfirm } from "@/shared/components/confirm/ConfirmProvider";
import type { KbDocument } from "@/types/api";

interface DocumentTableProps {
  documents: KbDocument[];
}

function statusVariant(
  status: KbDocument["status"],
): "success" | "warning" | "destructive" | "secondary" {
  switch (status) {
    case "ready":
      return "success";
    case "processing":
      return "warning";
    case "error":
      return "destructive";
    default:
      return "secondary";
  }
}

function statusLabel(status: KbDocument["status"]): string {
  switch (status) {
    case "ready":
      return "Pronto";
    case "processing":
      return "Processando";
    case "error":
      return "Erro";
    default:
      return "Pendente";
  }
}

export function DocumentTable({ documents }: DocumentTableProps) {
  const [rows, setRows] = useState<KbDocument[]>(documents);
  const [deleting, setDeleting] = useState<string | null>(null);
  const confirm = useConfirm();

  async function handleDelete(id: string) {
    const ok = await confirm({
      title: "Remover documento",
      description: "Tem certeza que deseja remover este documento da base de conhecimento? Esta ação não pode ser desfeita.",
      confirmLabel: "Remover",
      variant: "danger",
    });
    if (!ok) return;
    setDeleting(id);
    try {
      await deleteDocument(id);
      setRows((prev) => prev.filter((d) => d.id !== id));
    } catch (err) {
      alert(`Erro ao remover: ${err instanceof Error ? err.message : err}`);
    } finally {
      setDeleting(null);
    }
  }

  if (rows.length === 0) {
    return (
      <div className="rounded-md border p-8 text-center text-sm text-muted-foreground">
        Nenhum documento na base de conhecimento.{" "}
        <Link href="/kb/upload" className="underline">
          Faça o upload do primeiro documento.
        </Link>
      </div>
    );
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Arquivo</TableHead>
          <TableHead>Status</TableHead>
          <TableHead className="text-right">Chunks</TableHead>
          <TableHead>Criado em</TableHead>
          <TableHead className="w-12" />
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((doc) => (
          <TableRow key={doc.id}>
            <TableCell className="font-medium">{doc.filename}</TableCell>
            <TableCell>
              <Badge variant={statusVariant(doc.status)}>
                {statusLabel(doc.status)}
              </Badge>
            </TableCell>
            <TableCell className="text-right">{doc.chunk_count}</TableCell>
            <TableCell className="text-muted-foreground">
              {new Date(doc.created_at).toLocaleDateString("pt-BR")}
            </TableCell>
            <TableCell>
              <Button
                variant="ghost"
                size="icon"
                disabled={deleting === doc.id}
                onClick={() => handleDelete(doc.id)}
                aria-label="Remover documento"
              >
                <Trash2 className="h-4 w-4 text-muted-foreground" />
              </Button>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
