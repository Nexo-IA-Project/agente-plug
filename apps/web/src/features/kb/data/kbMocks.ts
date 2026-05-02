// apps/web/src/features/kb/data/kbMocks.ts
import type { KbFile } from "../types";

export const processedFiles: KbFile[] = [
  { id: "1", name: "manuais_tecnicos_v2.docx", size: "2.4 MB", status: "indexed" },
  { id: "2", name: "politicas_RH_2023.pdf", size: "1.1 MB", status: "indexed" },
  { id: "3", name: "log_servidor_corrompido.txt", size: "0.3 MB", status: "error" },
  { id: "4", name: "atas_reuniao_diretoria.pdf", size: "5.7 MB", status: "indexed" },
];
