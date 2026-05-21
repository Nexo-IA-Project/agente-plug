"use client";

import { useCallback, useEffect, useState } from "react";
import {
  createCourse,
  deleteCourse,
  listCourses,
  updateCourse,
} from "@/lib/api";
import type { Course, CreateCourseInput, UpdateCourseInput } from "../types";

export function useCourses() {
  const [courses, setCourses] = useState<Course[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const data = await listCourses();
      setCourses(data);
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const create = useCallback(
    async (input: CreateCourseInput): Promise<Course> => {
      const c = await createCourse(input);
      await refresh();
      return c;
    },
    [refresh]
  );

  const update = useCallback(
    async (id: string, input: UpdateCourseInput): Promise<Course> => {
      const c = await updateCourse(id, input);
      await refresh();
      return c;
    },
    [refresh]
  );

  const remove = useCallback(
    async (id: string): Promise<void> => {
      await deleteCourse(id);
      await refresh();
    },
    [refresh]
  );

  return { courses, loading, error, refresh, create, update, remove };
}
