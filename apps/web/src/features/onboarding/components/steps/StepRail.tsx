"use client";

export type StepIndex = 1 | 2 | 3;
export type StepStatus = "done" | "current" | "pending" | "locked";

export interface StepDescriptor {
  index: StepIndex;
  label: string;
  status: StepStatus;
  hint?: string;
}

interface StepRailProps {
  steps: StepDescriptor[];
  onNavigate: (index: StepIndex) => void;
}

export function StepRail({ steps, onNavigate }: StepRailProps) {
  return (
    <ol className="flex flex-col gap-0 pr-6">
      {steps.map((step, i) => (
        <li key={step.index} className="flex items-stretch gap-3">
          <div className="flex flex-col items-center">
            <NodeButton step={step} onClick={() => onNavigate(step.index)} />
            {i < steps.length - 1 && (
              <div
                className={`my-1 w-0.5 flex-1 min-h-6 ${
                  step.status === "done"
                    ? "bg-emerald-500"
                    : "bg-outline-variant"
                }`}
              />
            )}
          </div>
          <div className="pb-6 pt-1">
            <p
              className={`text-sm font-medium ${
                step.status === "current"
                  ? "text-on-surface"
                  : step.status === "done"
                    ? "text-emerald-500"
                    : "text-on-surface-variant"
              }`}
            >
              {step.label}
            </p>
            {step.hint && (
              <p className="mt-0.5 text-xs text-on-surface-variant">
                {step.hint}
              </p>
            )}
          </div>
        </li>
      ))}
    </ol>
  );
}

function NodeButton({
  step,
  onClick,
}: {
  step: StepDescriptor;
  onClick: () => void;
}) {
  const isLocked = step.status === "locked";
  const isDone = step.status === "done";
  const isCurrent = step.status === "current";

  return (
    <button
      type="button"
      onClick={onClick}
      disabled={isLocked}
      aria-current={isCurrent ? "step" : undefined}
      className={`flex h-10 w-10 items-center justify-center rounded-full border-2 font-semibold text-sm transition-all
        ${
          isCurrent
            ? "border-transparent bg-primary text-on-primary shadow-md shadow-primary/30"
            : isDone
              ? "border-transparent bg-emerald-500 text-white"
              : isLocked
                ? "cursor-not-allowed border-outline-variant bg-surface-container text-on-surface-variant opacity-60"
                : "border-outline-variant bg-surface-container text-on-surface-variant hover:bg-surface-container-high"
        }`}
    >
      {isDone ? (
        <span className="material-symbols-outlined text-base">check</span>
      ) : (
        step.index
      )}
    </button>
  );
}
