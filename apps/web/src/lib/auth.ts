// apps/web/src/lib/auth.ts

const TOKEN_COOKIE = "nexoia_token";
const TOKEN_KEY = "nexoia_token";
const MAX_AGE = 60 * 60 * 24 * 7; // 7 days

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  const stored = localStorage.getItem(TOKEN_KEY);
  if (stored) return stored;
  // fallback: cookie (caso localStorage seja limpo externamente)
  const match = document.cookie.match(/(?:^|;\s*)nexoia_token=([^;]*)/);
  return match ? decodeURIComponent(match[1]) : null;
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
  document.cookie = `${TOKEN_COOKIE}=${encodeURIComponent(token)}; path=/; samesite=lax; max-age=${MAX_AGE}`;
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
  document.cookie = `${TOKEN_COOKIE}=; path=/; max-age=0`;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type AccountOption = {
  membership_id: string;
  account_id: string;
  account_name: string;
  role: "admin" | "operator";
  is_owner: boolean;
};

export type LoginResult =
  | { status: "authenticated"; access_token: string }
  | { status: "choose_account"; pre_auth_token: string; accounts: AccountOption[] }
  | { status: "must_change_password"; pre_auth_token: string };

export async function loginRequest(
  email: string,
  password: string,
): Promise<LoginResult> {
  const res = await fetch(`${API_URL}/admin/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(
      typeof body.detail === "string" ? body.detail : "Credenciais inválidas",
    );
  }

  return (await res.json()) as LoginResult;
}

export async function selectAccount(
  preAuthToken: string,
  accountId: string,
): Promise<string> {
  const res = await fetch(`${API_URL}/admin/auth/select-account`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${preAuthToken}`,
    },
    body: JSON.stringify({ account_id: accountId }),
  });
  if (!res.ok) throw new Error("Falha ao selecionar empresa");
  const data = (await res.json()) as { access_token: string };
  return data.access_token;
}

export async function switchAccount(accountId: string): Promise<string> {
  const token = getToken();
  const res = await fetch(`${API_URL}/admin/auth/switch-account`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token ?? ""}`,
    },
    body: JSON.stringify({ account_id: accountId }),
  });
  if (!res.ok) throw new Error("Falha ao trocar de empresa");
  const data = (await res.json()) as { access_token: string };
  return data.access_token;
}
