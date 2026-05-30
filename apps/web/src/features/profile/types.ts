// apps/web/src/features/profile/types.ts

export interface MeResponse {
  id: string;
  name: string;
  email: string;
  role: "admin" | "operator";
  must_change_password: boolean;
  has_avatar: boolean;
  permissions: string[];
}
