"use client";

import { useState } from "react";
import { useCourses } from "@/features/courses/hooks/useCourses";
import { CourseCard } from "@/features/courses/components/CourseCard";
import { CourseDrawer } from "@/features/courses/components/CourseDrawer";
import { useToast } from "@/shared/hooks/useToast";
import { Course } from "@/features/courses/types";

export default function CoursesPage() {
  const { courses, loading, error, create, update, remove } = useCourses();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [editing, setEditing] = useState<Course | null>(null);
  const toast = useToast();

  const openCreate = () => {
    setEditing(null);
    setDrawerOpen(true);
  };
  const openEdit = (c: Course) => {
    setEditing(c);
    setDrawerOpen(true);
  };

  const handleSubmit = async (input: { name: string; hubla_id: string; is_active?: boolean }) => {
    try {
      if (editing) {
        await update(editing.id, input);
        toast.success("Curso atualizado");
      } else {
        await create(input);
        toast.success("Curso criado");
      }
    } catch (e) {
      const msg = (e as Error).message;
      if (msg.includes("409")) {
        toast.error("Já existe curso com esse ID Hubla");
      } else {
        toast.error("Falha ao salvar curso", msg);
      }
      throw e;
    }
  };

  const handleDelete = async (c: Course) => {
    if (!confirm(`Remover o curso "${c.name}"?`)) return;
    try {
      await remove(c.id);
      toast.success("Curso removido");
    } catch (e) {
      const msg = (e as Error).message;
      if (msg.includes("409")) {
        toast.warning("Não é possível remover", "Existem follow-ups vinculados a este curso.");
      } else {
        toast.error("Falha ao remover", msg);
      }
    }
  };

  return (
    <div className="flex flex-col gap-6 p-8">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-on-surface">Cursos</h1>
          <p className="text-sm text-on-surface-variant">
            Cadastre os cursos vendidos para que os follow-ups possam ser disparados.
          </p>
        </div>
        <button
          onClick={openCreate}
          className="flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-on-primary"
        >
          <span className="material-symbols-outlined">add</span>
          Novo curso
        </button>
      </header>

      {loading && <p className="text-on-surface-variant">Carregando...</p>}
      {error && <p className="text-error">{error}</p>}
      {!loading && courses.length === 0 && (
        <div className="rounded-lg border border-dashed border-outline-variant p-8 text-center text-on-surface-variant">
          Nenhum curso cadastrado ainda.
        </div>
      )}

      <div className="flex flex-col gap-3">
        {courses.map((c) => (
          <CourseCard
            key={c.id}
            course={c}
            onEdit={() => openEdit(c)}
            onDelete={() => handleDelete(c)}
          />
        ))}
      </div>

      <CourseDrawer
        open={drawerOpen}
        course={editing}
        onClose={() => setDrawerOpen(false)}
        onSubmit={handleSubmit}
      />
    </div>
  );
}
