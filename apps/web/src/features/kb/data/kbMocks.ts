// apps/web/src/features/kb/data/kbMocks.ts
import type { KbFile } from "../types";

export const processedFiles: KbFile[] = [
  { id: "1", name: "politica_privacidade_v2.pdf", size: "2.4 MB", status: "indexed" },
  { id: "2", name: "contrato_fornecedores_2024.docx", size: "1.1 MB", status: "indexed" },
  { id: "3", name: "logs_servidor_janeiro.txt", size: "8.5 MB", status: "processing" },
  { id: "4", name: "manual_de_marca_2024.docx", size: "5.7 MB", status: "indexed" },
  { id: "5", name: "relatorio_financeiro_q3.pdf", size: "3.2 MB", status: "indexed" },
];
