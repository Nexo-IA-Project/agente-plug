// apps/web/src/features/profile/types.ts

export interface MeResponse {
  id: string;
  name: string;
  email: string;
  role: "admin" | "operator";
  must_change_password: boolean;
  has_avatar: boolean;
}

export interface SmtpConfig {
  host: string;
  port: number;
  username: string;
  use_tls: boolean;
  from_name: string;
  from_email: string;
  has_password: boolean;
}

export interface SmtpConfigInput {
  host: string;
  port: number;
  username: string;
  password: string | null;
  use_tls: boolean;
  from_name: string;
  from_email: string;
}
