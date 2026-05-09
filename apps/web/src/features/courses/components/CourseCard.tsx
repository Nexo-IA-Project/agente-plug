"use client";

import type { Course } from "../types";

interface Props {
  course: Course;
  onEdit: () => void;
  onDelete: () => void;
}

export function CourseCard({ course, onEdit, onDelete }: Props) {
  return (
    <article className="flex items-center justify-between rounded-lg border border-outline-variant bg-surface-container p-4">
      <div className="flex flex-col gap-1">
        <div className="flex items-center gap-2">
          <h3 className="text-base font-semibold text-on-surface">{course.name}</h3>
          {!course.is_active && (
            <span className="rounded-full bg-surface-container-high px-2 py-0.5 text-xs text-on-surface-variant">
              Inativo
            </span>
          )}
        </div>
        <code className="text-xs text-on-surface-variant">{course.hubla_id}</code>
        <span className="text-xs text-on-surface-variant">
          {course.flow_count} follow-up{course.flow_count === 1 ? "" : "s"} vinculado
          {course.flow_count === 1 ? "" : "s"}
        </span>
      </div>
      <div className="flex gap-2">
        <button
          type="button"
          onClick={onEdit}
          className="rounded-md p-2 text-on-surface-variant hover:bg-surface-container-high"
          aria-label="Editar"
        >
          <span className="material-symbols-outlined">edit</span>
        </button>
        <button
          type="button"
          onClick={onDelete}
          className="rounded-md p-2 text-on-surface-variant hover:bg-surface-container-high"
          aria-label="Excluir"
        >
          <span className="material-symbols-outlined">delete</span>
        </button>
      </div>
    </article>
  );
}
