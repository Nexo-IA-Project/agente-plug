// apps/web/src/features/users/types.ts

export type UserRole = "admin" | "operator";

export interface User {
  /** ID do vínculo (membership), não da identidade. */
  id: string;
  name: string;
  email: string;
  role: UserRole;
  /** Dono da conta — protegido pela plataforma (não editável/excluível). */
  is_owner: boolean;
  is_active: boolean;
  must_change_password: boolean;
  has_avatar: boolean;
  created_at: string;
  last_login_at: string | null;
  profile_id: string | null;
  profile_name: string | null;
}

export interface UserListResponse {
  items: User[];
  total: number;
  page: number;
  page_size: number;
}

export interface CreateUserInput {
  name: string;
  email: string;
  role: UserRole;
  profile_id: string | null;
}

export interface UpdateUserInput {
  name: string;
  role: UserRole;
  is_active: boolean;
  profile_id: string | null;
}
