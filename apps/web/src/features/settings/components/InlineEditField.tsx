"use client";

import { useState, useRef, useEffect } from "react";

interface InlineEditFieldProps {
  label: string;
  value: string | number;
  type?: "text" | "secret" | "url" | "number";
  placeholder?: string;
  description?: string;
  step?: number;
  onSave: (value: string | number) => Promise<boolean>;
  readOnly?: boolean;
}

export function InlineEditField({
  label,
  value,
  type = "text",
  placeholder,
  description,
  step,
  onSave,
  readOnly = false,
}: InlineEditFieldProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [editValue, setEditValue] = useState("");
  const [saving, setSaving] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (isEditing && inputRef.current) {
      inputRef.current.focus();
    }
  }, [isEditing]);

  function startEdit() {
    if (readOnly) return;
    setEditValue("");
    setIsEditing(true);
  }

  function cancelEdit() {
    setIsEditing(false);
    setEditValue("");
  }

  async function handleSave() {
    if (!editValue && type !== "number") return;
    setSaving(true);
    const val = type === "number" ? Number(editValue) : editValue;
    const ok = await onSave(val);
    setSaving(false);
    if (ok) setIsEditing(false);
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter") handleSave();
    if (e.key === "Escape") cancelEdit();
  }

  const isSecret = type === "secret";
  const displayValue = String(value);
  const isEmpty = !displayValue || displayValue === "0";

  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-center justify-between">
        <label className="text-xs font-semibold uppercase tracking-wide text-on-surface-variant">
          {label}
        </label>
        {description && (
          <span className="text-xs text-on-surface-variant/60">{description}</span>
        )}
      </div>

      <div
        className={[
          "relative overflow-hidden rounded-xl border transition-all duration-200",
          isEditing
            ? "border-primary ring-2 ring-primary/20 bg-surface-container"
            : readOnly
              ? "border-outline-variant bg-surface-container"
              : "border-outline-variant bg-surface-container hover:border-outline cursor-pointer",
        ].join(" ")}
      >
        {/* Static display (not editing) */}
        <div
          className={[
            "flex items-center justify-between px-4 py-3 transition-all duration-200",
            isEditing ? "opacity-0 absolute inset-0 pointer-events-none" : "opacity-100",
          ].join(" ")}
          onClick={startEdit}
        >
          <span
            className={[
              "font-mono text-sm",
              isEmpty ? "text-on-surface-variant/40 italic" : "text-on-surface",
            ].join(" ")}
          >
            {isEmpty ? (placeholder || "Não configurado") : displayValue}
          </span>
          {!readOnly && (
            <button
              type="button"
              onClick={(e) => { e.stopPropagation(); startEdit(); }}
              className="ml-2 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg text-on-surface-variant transition-colors hover:bg-surface-container-high hover:text-on-surface"
              aria-label={`Editar ${label}`}
            >
              <span className="material-symbols-outlined" style={{ fontSize: "16px" }}>edit</span>
            </button>
          )}
        </div>

        {/* Edit mode */}
        <div
          className={[
            "flex items-center gap-2 px-4 py-3 transition-all duration-200",
            isEditing ? "opacity-100" : "opacity-0 absolute inset-0 pointer-events-none",
          ].join(" ")}
        >
          <input
            ref={inputRef}
            type={isSecret ? "password" : type === "number" ? "number" : "text"}
            step={step}
            value={editValue}
            onChange={(e) => setEditValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={isSecret ? "Novo valor" : (placeholder || "")}
            className="flex-1 bg-transparent text-sm text-on-surface placeholder:text-on-surface-variant/40 focus:outline-none"
          />
          <div className="flex shrink-0 items-center gap-1">
            <button
              type="button"
              onClick={handleSave}
              disabled={saving || (!editValue && type !== "number")}
              className="flex items-center gap-1.5 rounded-lg bg-primary px-3 py-1.5 text-xs font-semibold text-on-primary transition-opacity hover:opacity-90 disabled:opacity-40"
            >
              {saving ? (
                <span className="material-symbols-outlined animate-spin" style={{ fontSize: "14px" }}>progress_activity</span>
              ) : (
                <span className="material-symbols-outlined" style={{ fontSize: "14px" }}>check</span>
              )}
              Salvar
            </button>
            <button
              type="button"
              onClick={cancelEdit}
              className="flex h-8 w-8 items-center justify-center rounded-lg text-on-surface-variant transition-colors hover:bg-surface-container-high hover:text-on-surface"
              aria-label="Cancelar"
            >
              <span className="material-symbols-outlined" style={{ fontSize: "16px" }}>close</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
