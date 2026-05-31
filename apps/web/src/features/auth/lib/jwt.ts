export interface AuthTokenPayload {
  sub: string;         // email
  user_id: string;
  identity_id: string;
  account_id: string;  // UUID
  membership_id: string;
  role: "admin" | "operator";
  must_change_password: boolean;
  exp: number;
}

export function decodeJwt(token: string): AuthTokenPayload | null {
  try {
    const payload = token.split(".")[1];
    const decoded = atob(payload.replace(/-/g, "+").replace(/_/g, "/"));
    return JSON.parse(decoded) as AuthTokenPayload;
  } catch {
    return null;
  }
}
