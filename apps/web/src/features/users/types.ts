// apps/web/src/features/users/types.ts

export type UserRole = "admin" | "operator";

export interface User {
  id: string;
  name: string;
  email: string;
  role: UserRole;
  is_active: boolean;
  must_change_password: boolean;
  has_avatar: boolean;
  created_at: string;
  last_login_at: string | null;
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
}

export interface UpdateUserInput {
  name: string;
  role: UserRole;
  is_active: boolean;
}
