import type { TemplateStatus } from "../types";

const STATUS_STYLES: Record<TemplateStatus, string> = {
  APPROVED: "bg-success/20 text-success",
  PENDING: "bg-warning/20 text-warning",
  REJECTED: "bg-error/20 text-error",
};

const STATUS_LABELS: Record<TemplateStatus, string> = {
  APPROVED: "Aprovado",
  PENDING: "Pendente",
  REJECTED: "Rejeitado",
};

export function TemplateStatusBadge({ status }: { status: TemplateStatus }) {
  return (
    <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${STATUS_STYLES[status]}`}>
      {STATUS_LABELS[status]}
    </span>
  );
}
