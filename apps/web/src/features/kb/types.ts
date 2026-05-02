// apps/web/src/features/kb/types.ts

export type FileStatus = "indexed" | "error" | "processing";

export interface KbFile {
  id: string;
  name: string;
  size: string;
  status: FileStatus;
}
