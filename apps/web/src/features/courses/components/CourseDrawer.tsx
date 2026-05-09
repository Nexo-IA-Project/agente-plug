"use client";

import { useEffect, useState } from "react";
import { Drawer } from "@/shared/components/Drawer";
import type { Course, CreateCourseInput } from "../types";

interface Props {
  open: boolean;
  course: Course | null;
  onClose: () => void;
  onSubmit: (input: CreateCourseInput) => Promise<void>;
}

export function CourseDrawer({ open, course, onClose, onSubmit }: Props) {
  const [name, setName] = useState("");
  const [hublaId, setHublaId] = useState("");
  const [isActive, setIsActive] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (course) {
      setName(course.name);
      setHublaId(course.hubla_id);
      setIsActive(course.is_active);
    } else {
      setName("");
      setHublaId("");
      setIsActive(true);
    }
  }, [course, open]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      await onSubmit({ name, hubla_id: hublaId, is_active: isActive });
      onClose();
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Drawer
      open={open}
      onClose={onClose}
      title={course ? `Editar curso — ${course.name}` : "Novo curso"}
      footer={
        <div className="flex justify-end gap-3">
          <button
            type="button"
            onClick={onClose}
            className="rounded-md px-4 py-2 text-on-surface-variant hover:bg-surface-container-high"
          >
            Cancelar
          </button>
          <button
            type="submit"
            form="course-form"
            disabled={submitting || !name || !hublaId}
            className="rounded-md bg-primary px-4 py-2 text-on-primary disabled:opacity-50"
          >
            {submitting ? "Salvando..." : "Salvar"}
          </button>
        </div>
      }
    >
      <form id="course-form" onSubmit={handleSubmit} className="flex flex-col gap-6">
        <label className="flex flex-col gap-2">
          <span className="text-sm font-medium text-on-surface">Nome</span>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="rounded-md border border-outline-variant bg-surface px-3 py-2 text-on-surface"
            placeholder="Ex: Marketing 360"
            required
          />
        </label>
        <label className="flex flex-col gap-2">
          <span className="text-sm font-medium text-on-surface">ID na Hubla</span>
          <input
            type="text"
            value={hublaId}
            onChange={(e) => setHublaId(e.target.value)}
            className="rounded-md border border-outline-variant bg-surface px-3 py-2 font-mono text-sm text-on-surface"
            placeholder="Ex: prod-mkt-360"
            required
          />
          <span className="text-xs text-on-surface-variant">
            Deve casar com o campo <code>product_id</code> que vem no webhook da Hubla.
          </span>
        </label>
        <label className="flex items-center gap-3">
          <input
            type="checkbox"
            checked={isActive}
            onChange={(e) => setIsActive(e.target.checked)}
            className="h-4 w-4"
          />
          <span className="text-sm text-on-surface">Curso ativo</span>
        </label>
      </form>
    </Drawer>
  );
}
