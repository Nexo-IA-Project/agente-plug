"use client";

import { useState } from "react";
import { useToast } from "@/shared/hooks/useToast";
import type {
  FollowupEnrollmentDetail,
  FollowupStepDetail,
  FollowupStepStatus,
} from "../types";

// ─────────────────────────────────────────────────────────────────────────────
// Style tokens por status — palette semântica alinhada ao resto do projeto
// (emerald = sent, amber = pending, rose = failed, slate/outline = cancelled).
// ─────────────────────────────────────────────────────────────────────────────

interface StatusVisual {
  /** Cor de fill do node circular */
  nodeBg: string;
  /** Ring colorido ao redor do node */
  nodeRing: string;
  /** Cor do connector vertical descendo do node */
  connector: string;
  /** Estilo da linha (solid|dashed) */
  connectorStyle: "solid" | "dashed";
  /** Cor do hint text de status (pill no canto direito) */
  hintText: string;
  /** Background do pill de status */
  pillBg: string;
  /** Ícone Material Symbols */
  icon: string;
  /** Label PT-BR humano */
  label: string;
}

// Pills e textos com 2 tons: claro pra light mode (text-X-700), escuro pra dark
// (text-X-300). Backgrounds em /15 ficam invisíveis em light → uso /20 ou solid.
const STATUS_VISUAL: Record<FollowupStepStatus, StatusVisual> = {
  sent: {
    nodeBg: "bg-emerald-500",
    nodeRing: "ring-emerald-500/40",
    connector: "bg-emerald-500/50",
    connectorStyle: "solid",
    hintText: "text-emerald-700 dark:text-emerald-400",
    pillBg:
      "bg-emerald-500/20 text-emerald-800 border border-emerald-600/40 dark:bg-emerald-500/15 dark:text-emerald-300 dark:border-emerald-500/30",
    icon: "check_circle",
    label: "enviada",
  },
  pending: {
    nodeBg: "bg-amber-500/30",
    nodeRing: "ring-amber-500/50",
    connector: "bg-outline-variant/60",
    connectorStyle: "dashed",
    hintText: "text-amber-700 dark:text-amber-400",
    pillBg:
      "bg-amber-500/20 text-amber-800 border border-amber-600/40 dark:bg-amber-500/15 dark:text-amber-300 dark:border-amber-500/30",
    icon: "schedule",
    label: "agendada",
  },
  failed: {
    nodeBg: "bg-rose-500",
    nodeRing: "ring-rose-500/40",
    connector: "bg-rose-500/40",
    connectorStyle: "solid",
    hintText: "text-rose-700 dark:text-rose-400",
    pillBg:
      "bg-rose-500/20 text-rose-800 border border-rose-600/40 dark:bg-rose-500/15 dark:text-rose-300 dark:border-rose-500/30",
    icon: "error",
    label: "falhou",
  },
  cancelled: {
    nodeBg: "bg-on-surface-variant/30",
    nodeRing: "ring-on-surface-variant/30",
    connector: "bg-outline-variant/40",
    connectorStyle: "dashed",
    hintText: "text-on-surface-variant",
    pillBg: "bg-surface-container-high text-on-surface-variant border border-outline-variant",
    icon: "cancel",
    label: "cancelada",
  },
};

// ─────────────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────────────

function formatTime(d: string | null): string {
  if (!d) return "—";
  const dt = new Date(d);
  return dt.toLocaleTimeString("pt-BR", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function formatDateTime(d: string | null): string {
  if (!d) return "—";
  const dt = new Date(d);
  return dt.toLocaleString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatDelay(minutes: number): string {
  if (minutes === 0) return "imediato";
  if (minutes < 60) return `${minutes} min após compra`;
  if (minutes < 1440) {
    const hours = Math.floor(minutes / 60);
    const rem = minutes % 60;
    return rem === 0
      ? `${hours}h após compra`
      : `${hours}h ${rem}min após compra`;
  }
  const days = Math.floor(minutes / 1440);
  return `${days}d após compra`;
}

// ─────────────────────────────────────────────────────────────────────────────
// Step row
// ─────────────────────────────────────────────────────────────────────────────

interface StepNodeProps {
  step: FollowupStepDetail;
  isLast: boolean;
  onDispatch: (stepId: string) => Promise<void>;
}

function StepNode({ step, isLast, onDispatch }: StepNodeProps) {
  const visual = STATUS_VISUAL[step.status];
  const [busy, setBusy] = useState(false);

  const canAct = step.status === "pending" || step.status === "failed";
  const actionLabel = step.status === "failed" ? "Retentar" : "Disparar agora";
  const actionIcon = step.status === "failed" ? "refresh" : "bolt";

  const handleClick = async () => {
    if (busy) return;
    setBusy(true);
    try {
      await onDispatch(step.id);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="relative flex gap-4">
      {/* Coluna do node + connector vertical */}
      <div className="relative flex w-4 shrink-0 flex-col items-center">
        {/* Node circular com ring */}
        <div
          className={[
            "relative z-10 mt-1 flex h-3 w-3 shrink-0 items-center justify-center rounded-full ring-4",
            visual.nodeBg,
            visual.nodeRing,
            step.status === "pending" ? "animate-pulse" : "",
          ].join(" ")}
        />
        {/* Connector descendo (não desenha pro último step) */}
        {!isLast && (
          <div
            className={[
              "mt-1 w-px flex-1",
              visual.connector,
              visual.connectorStyle === "dashed"
                ? "[background-image:linear-gradient(to_bottom,currentColor_50%,transparent_50%)] [background-size:1px_6px] !bg-transparent"
                : "",
            ].join(" ")}
            style={
              visual.connectorStyle === "dashed"
                ? { color: "var(--color-outline-variant, #4b5563)" }
                : undefined
            }
          />
        )}
      </div>

      {/* Conteúdo do step */}
      <div className="flex-1 pb-5">
        {/* Linha 1: posição + template + status pill */}
        <div className="flex items-center gap-2">
          <span className="font-mono text-[11px] tabular-nums text-on-surface-variant">
            #{step.position}
          </span>
          {step.template_name ? (
            <code className="rounded bg-surface-container px-1.5 py-0.5 font-mono text-[12px] font-medium text-on-surface">
              {step.template_name}
            </code>
          ) : (
            <span className="text-[12px] italic text-on-surface-variant">texto livre</span>
          )}
          <span
            className={[
              "ml-auto inline-flex shrink-0 items-center gap-1 rounded-sm px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wider",
              visual.pillBg,
            ].join(" ")}
          >
            <span className="material-symbols-outlined" style={{ fontSize: "12px" }}>
              {visual.icon}
            </span>
            {visual.label}
          </span>
        </div>

        {/* Linha 2: timestamp + delay info */}
        <div className="mt-1 flex items-center gap-1.5 font-mono text-[10px] tabular-nums text-on-surface-variant">
          <span>
            {step.status === "sent"
              ? formatTime(step.sent_at)
              : step.status === "pending"
              ? formatTime(step.scheduled_for)
              : step.status === "failed"
              ? formatTime(step.sent_at)
              : "—"}
          </span>
          <span className="opacity-50">·</span>
          <span className="lowercase">{formatDelay(step.delay_from_previous_minutes)}</span>
        </div>

        {/* Linha 3: preview do body renderizado (só sent/failed) */}
        {step.rendered_preview && (step.status === "sent" || step.status === "failed") && (
          <p className="mt-1.5 line-clamp-2 text-[12px] leading-snug text-on-surface-variant/80">
            {step.rendered_preview}
          </p>
        )}

        {/* Linha 4: banner do motivo de falha */}
        {step.status === "failed" && step.failure_reason && (
          <div className="mt-2 border-l-2 border-rose-500 bg-rose-500/5 py-1 pl-2 pr-1.5">
            <p className="font-mono text-[10.5px] leading-snug text-rose-300">
              <span className="material-symbols-outlined mr-1 align-middle" style={{ fontSize: "11px" }}>
                error
              </span>
              {step.failure_reason}
            </p>
          </div>
        )}

        {/* Pending sem preview ainda */}
        {step.status === "pending" && (
          <p className="mt-1.5 text-[11.5px] italic text-on-surface-variant/60">
            Aguardando envio…
          </p>
        )}

        {/* Action button — só pra steps actionáveis */}
        {canAct && (
          <button
            onClick={() => void handleClick()}
            disabled={busy}
            className={[
              "mt-2 inline-flex items-center gap-1.5 rounded-sm border px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wider transition-all",
              step.status === "failed"
                ? "border-rose-600 bg-rose-500/10 text-rose-700 hover:bg-rose-500/20 hover:border-rose-700 dark:border-rose-500/40 dark:text-rose-300 dark:hover:bg-rose-500/10"
                : "border-amber-600 bg-amber-500/10 text-amber-800 hover:bg-amber-500/20 hover:border-amber-700 dark:border-amber-500/40 dark:text-amber-300 dark:hover:bg-amber-500/10",
              "disabled:cursor-wait disabled:opacity-60",
            ].join(" ")}
          >
            {busy ? (
              <span
                className="material-symbols-outlined animate-spin"
                style={{ fontSize: "13px" }}
              >
                progress_activity
              </span>
            ) : (
              <span className="material-symbols-outlined" style={{ fontSize: "13px" }}>
                {actionIcon}
              </span>
            )}
            {busy ? "Disparando…" : actionLabel}
          </button>
        )}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Enrollment card
// ─────────────────────────────────────────────────────────────────────────────

interface EnrollmentCardProps {
  enrollment: FollowupEnrollmentDetail;
  onDispatchStep: (enrollmentId: string, stepId: string) => Promise<void>;
}

function EnrollmentCard({ enrollment, onDispatchStep }: EnrollmentCardProps) {
  // Cor de "vibe" do card baseado no estado geral
  const hasFailed = enrollment.steps.some((s) => s.status === "failed");
  const hasPending = enrollment.steps.some((s) => s.status === "pending");
  const allDone = enrollment.steps.every((s) => s.status === "sent");

  const accent = hasFailed
    ? "border-l-rose-500/60"
    : hasPending
    ? "border-l-amber-500/60"
    : allDone
    ? "border-l-emerald-500/60"
    : "border-l-outline-variant";

  return (
    <article
      className={[
        "animate-fade-in border border-outline-variant border-l-[3px] bg-surface-container-low",
        accent,
      ].join(" ")}
    >
      {/* Header do enrollment */}
      <header className="border-b border-outline-variant/50 px-4 py-3">
        <div className="flex items-center gap-2">
          <span
            className="material-symbols-outlined text-amber-400"
            style={{ fontSize: "16px" }}
          >
            bolt
          </span>
          <h4 className="truncate text-[13px] font-semibold text-on-surface">
            {enrollment.flow_name}
          </h4>
        </div>
        <p className="mt-0.5 font-mono text-[10px] tabular-nums text-on-surface-variant">
          {formatDateTime(enrollment.enrolled_at)}
          <span className="mx-1.5 opacity-50">·</span>
          {enrollment.trigger_event_type}
        </p>
      </header>

      {/* Steps */}
      <div className="px-4 py-4">
        {enrollment.steps.length === 0 ? (
          <p className="text-center text-[12px] italic text-on-surface-variant">
            Nenhuma mensagem na sequência.
          </p>
        ) : (
          enrollment.steps.map((step, idx) => (
            <StepNode
              key={step.id}
              step={step}
              isLast={idx === enrollment.steps.length - 1}
              onDispatch={(stepId) => onDispatchStep(enrollment.id, stepId)}
            />
          ))
        )}
      </div>
    </article>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Timeline raiz (exportada)
// ─────────────────────────────────────────────────────────────────────────────

interface Props {
  enrollments: FollowupEnrollmentDetail[];
  /** Disparar/retentar um step. Backend retorna o novo status. */
  onDispatchStep: (enrollmentId: string, stepId: string) => Promise<void>;
}

export function FollowupTimeline({ enrollments, onDispatchStep }: Props) {
  const toast = useToast();
  const activeCount = enrollments.filter((e) =>
    e.steps.some((s) => s.status === "pending" || s.status === "failed"),
  ).length;

  const handleDispatch = async (enrollmentId: string, stepId: string) => {
    try {
      await onDispatchStep(enrollmentId, stepId);
      toast.success("Disparo concluído");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Falha ao disparar");
    }
  };

  return (
    <section>
      {/* Cabeçalho da seção */}
      <div className="mb-3 flex items-center justify-between">
        <p className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-on-surface-variant">
          <span className="material-symbols-outlined" style={{ fontSize: "14px" }}>
            schedule_send
          </span>
          Follow-ups
        </p>
        {activeCount > 0 && (
          <span className="inline-flex items-center gap-1 rounded-sm border border-amber-600/50 bg-amber-500/15 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-amber-800 dark:border-amber-500/40 dark:bg-amber-500/10 dark:text-amber-300">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-amber-500 dark:bg-amber-400" />
            {activeCount} {activeCount === 1 ? "ativo" : "ativos"}
          </span>
        )}
      </div>

      {/* Lista de enrollments OU empty state */}
      {enrollments.length === 0 ? (
        <div className="flex flex-col items-center gap-2 border border-dashed border-outline-variant bg-surface-container-low/40 px-4 py-8 text-center">
          <span
            className="material-symbols-outlined text-on-surface-variant/50"
            style={{ fontSize: "28px" }}
          >
            inbox
          </span>
          <p className="text-[12px] text-on-surface-variant">
            Nenhum follow-up disparado ainda.
          </p>
          <p className="text-[11px] text-on-surface-variant/70">
            Quando uma compra for registrada, os flows aparecem aqui.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {enrollments.map((e) => (
            <EnrollmentCard
              key={e.id}
              enrollment={e}
              onDispatchStep={handleDispatch}
            />
          ))}
        </div>
      )}
    </section>
  );
}
