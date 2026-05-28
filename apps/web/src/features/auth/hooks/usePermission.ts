"use client";

import { useAuth } from "./useAuth";

export type Action =
  | "manage_users"
  | "delete_template"
  | "delete_document"
  | "delete_api_token"
  | "edit_credentials"
  | "edit_smtp";

const ADMIN_ONLY: Action[] = [
  "manage_users",
  "delete_template",
  "delete_document",
  "delete_api_token",
  "edit_credentials",
  "edit_smtp",
];

export function usePermission() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const can = (action: Action): boolean => {
    if (ADMIN_ONLY.includes(action)) return isAdmin;
    return true;
  };
  return { isAdmin, can };
}
