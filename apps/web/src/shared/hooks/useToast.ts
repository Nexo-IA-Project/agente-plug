// apps/web/src/shared/hooks/useToast.ts
import { toast as sonnerToast } from "sonner";

export function useToast() {
  return {
    success: (message: string, description?: string) =>
      sonnerToast.success(message, { description }),
    error: (message: string, description?: string) =>
      sonnerToast.error(message, { description }),
    warning: (message: string, description?: string) =>
      sonnerToast.warning(message, { description }),
    info: (message: string, description?: string) =>
      sonnerToast.info(message, { description }),
  };
}
