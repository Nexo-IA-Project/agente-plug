"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Image from "next/image";
import { loginRequest, setToken } from "@/lib/auth";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const accountId = Number(process.env.NEXT_PUBLIC_ACCOUNT_ID ?? "1");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const token = await loginRequest(email, password, accountId);
      setToken(token);
      router.push("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao fazer login");
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <style>{`
        @keyframes fadeUp {
          from { opacity: 0; transform: translateY(16px); }
          to   { opacity: 1; transform: translateY(0); }
        }
        @keyframes glowPulse {
          0%, 100% { opacity: 0.15; transform: scale(1); }
          50%       { opacity: 0.25; transform: scale(1.05); }
        }
        @keyframes gridScroll {
          from { transform: translateY(0); }
          to   { transform: translateY(48px); }
        }
        .anim-1 { animation: fadeUp 0.55s cubic-bezier(.22,1,.36,1) both; }
        .anim-2 { animation: fadeUp 0.55s cubic-bezier(.22,1,.36,1) 0.07s both; }
        .anim-3 { animation: fadeUp 0.55s cubic-bezier(.22,1,.36,1) 0.14s both; }
        .anim-4 { animation: fadeUp 0.55s cubic-bezier(.22,1,.36,1) 0.21s both; }
        .anim-5 { animation: fadeUp 0.55s cubic-bezier(.22,1,.36,1) 0.28s both; }
        .anim-6 { animation: fadeUp 0.55s cubic-bezier(.22,1,.36,1) 0.35s both; }

        .login-input {
          width: 100%;
          background: rgba(10, 10, 12, 0.7);
          border: 1px solid rgba(60, 60, 70, 0.6);
          border-radius: 10px;
          padding: 13px 16px;
          color: #e4e2e4;
          font-size: 14px;
          font-family: var(--font-sans), sans-serif;
          outline: none;
          transition: border-color 0.2s, box-shadow 0.2s;
        }
        .login-input::placeholder { color: #525258; }
        .login-input:focus {
          border-color: #1e6fff;
          box-shadow: 0 0 0 3px rgba(30,111,255,0.12);
        }
        .login-input:hover:not(:focus) { border-color: rgba(80, 80, 95, 0.8); }

        .btn-login {
          width: 100%;
          padding: 13px 16px;
          background: linear-gradient(135deg, #1e6fff 0%, #0d4ed8 100%);
          border: none;
          border-radius: 10px;
          color: #fff;
          font-size: 14px;
          font-weight: 600;
          font-family: var(--font-sans), sans-serif;
          cursor: pointer;
          transition: opacity 0.2s, transform 0.15s, box-shadow 0.2s;
          box-shadow: 0 4px 24px rgba(30,111,255,0.3);
          letter-spacing: 0.01em;
        }
        .btn-login:hover:not(:disabled) {
          opacity: 0.92;
          transform: translateY(-1px);
          box-shadow: 0 6px 32px rgba(30,111,255,0.4);
        }
        .btn-login:active:not(:disabled) { transform: translateY(0); }
        .btn-login:disabled { opacity: 0.55; cursor: not-allowed; }

        .spinner {
          display: inline-block;
          width: 16px; height: 16px;
          border: 2px solid rgba(255,255,255,0.3);
          border-top-color: #fff;
          border-radius: 50%;
          animation: spin 0.65s linear infinite;
          vertical-align: middle;
          margin-right: 8px;
        }
        @keyframes spin { to { transform: rotate(360deg); } }

        .grid-bg {
          position: absolute; inset: 0;
          background-image:
            linear-gradient(rgba(30,111,255,0.04) 1px, transparent 1px),
            linear-gradient(90deg, rgba(30,111,255,0.04) 1px, transparent 1px);
          background-size: 48px 48px;
          animation: gridScroll 8s linear infinite;
        }

        .glow-orb {
          position: absolute;
          border-radius: 50%;
          animation: glowPulse 4s ease-in-out infinite;
          pointer-events: none;
        }
      `}</style>

      <div
        style={{
          display: "flex",
          minHeight: "100vh",
          background: "#080809",
          fontFamily: "var(--font-sans), sans-serif",
        }}
      >
        {/* ── LEFT BRAND PANEL ── */}
        <div
          style={{
            flex: "0 0 52%",
            position: "relative",
            overflow: "hidden",
            display: "flex",
            flexDirection: "column",
            justifyContent: "space-between",
            padding: "48px 56px",
          }}
        >
          {/* Animated grid */}
          <div className="grid-bg" />

          {/* Blue glow orbs */}
          <div
            className="glow-orb"
            style={{
              width: 600,
              height: 600,
              background:
                "radial-gradient(circle, rgba(30,111,255,0.18) 0%, transparent 70%)",
              bottom: -200,
              left: -100,
              animationDelay: "0s",
            }}
          />
          <div
            className="glow-orb"
            style={{
              width: 300,
              height: 300,
              background:
                "radial-gradient(circle, rgba(30,111,255,0.1) 0%, transparent 70%)",
              top: 80,
              right: 40,
              animationDelay: "2s",
            }}
          />

          {/* Huge XX watermark */}
          <div
            style={{
              position: "absolute",
              right: -60,
              top: "50%",
              transform: "translateY(-50%)",
              fontSize: 480,
              fontWeight: 900,
              color: "transparent",
              WebkitTextStroke: "1.5px rgba(30,111,255,0.08)",
              lineHeight: 1,
              userSelect: "none",
              fontFamily: "var(--font-sans), sans-serif",
              letterSpacing: "-0.05em",
              zIndex: 0,
            }}
          >
            ✕✕
          </div>

          {/* Logo */}
          <div style={{ position: "relative", zIndex: 1 }}>
            <Image
              src="/logo-dark.png"
              alt="NexoIA"
              width={200}
              height={56}
              style={{ objectFit: "contain", objectPosition: "left" }}
              priority
            />
          </div>

          {/* Center tagline */}
          <div style={{ position: "relative", zIndex: 1 }}>
            <p
              style={{
                fontSize: 13,
                color: "rgba(30,111,255,0.7)",
                letterSpacing: "0.15em",
                textTransform: "uppercase",
                fontWeight: 600,
                marginBottom: 16,
              }}
            >
              Plataforma de IA
            </p>
            <h1
              style={{
                fontSize: 48,
                fontWeight: 700,
                color: "#e4e2e4",
                lineHeight: 1.15,
                margin: 0,
                letterSpacing: "-0.02em",
              }}
            >
              Inteligência que
              <br />
              <span
                style={{
                  background: "linear-gradient(135deg, #1e6fff, #60a5fa)",
                  WebkitBackgroundClip: "text",
                  WebkitTextFillColor: "transparent",
                }}
              >
                conecta pessoas.
              </span>
            </h1>
            <p
              style={{
                marginTop: 20,
                fontSize: 15,
                color: "#525258",
                lineHeight: 1.6,
                maxWidth: 380,
              }}
            >
              Gerencie seus agentes de IA, base de conhecimento e integrações
              em um painel unificado.
            </p>
          </div>

          {/* Bottom version */}
          <div style={{ position: "relative", zIndex: 1 }}>
            <span
              style={{
                fontSize: 12,
                color: "#2a2a2e",
                fontFamily: "var(--font-mono), monospace",
              }}
            >
              v2025 · NexoIA Admin
            </span>
          </div>
        </div>

        {/* ── RIGHT FORM PANEL ── */}
        <div
          style={{
            flex: "0 0 48%",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            background: "#0c0c0e",
            borderLeft: "1px solid rgba(255,255,255,0.04)",
            padding: "48px 40px",
          }}
        >
          <div style={{ width: "100%", maxWidth: 380 }}>
            {/* Small logo for mobile/form context */}
            <div className="anim-1" style={{ marginBottom: 40 }}>
              <div
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  justifyContent: "center",
                  width: 44,
                  height: 44,
                  background: "rgba(30,111,255,0.1)",
                  border: "1px solid rgba(30,111,255,0.2)",
                  borderRadius: 12,
                  marginBottom: 24,
                }}
              >
                <span style={{ fontSize: 20, color: "#1e6fff" }}>✕</span>
              </div>
              <h2
                style={{
                  fontSize: 26,
                  fontWeight: 700,
                  color: "#e4e2e4",
                  margin: "0 0 6px",
                  letterSpacing: "-0.02em",
                }}
              >
                Acessar painel
              </h2>
              <p style={{ fontSize: 14, color: "#525258", margin: 0 }}>
                Entre com suas credenciais de administrador.
              </p>
            </div>

            <form onSubmit={handleSubmit}>
              {/* Email */}
              <div className="anim-2" style={{ marginBottom: 14 }}>
                <label
                  style={{
                    display: "block",
                    fontSize: 12,
                    fontWeight: 600,
                    color: "#909097",
                    letterSpacing: "0.06em",
                    textTransform: "uppercase",
                    marginBottom: 8,
                  }}
                >
                  E-mail
                </label>
                <input
                  className="login-input"
                  type="email"
                  placeholder="admin@exemplo.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  autoComplete="email"
                  autoFocus
                />
              </div>

              {/* Password */}
              <div className="anim-3" style={{ marginBottom: 28, position: "relative" }}>
                <label
                  style={{
                    display: "block",
                    fontSize: 12,
                    fontWeight: 600,
                    color: "#909097",
                    letterSpacing: "0.06em",
                    textTransform: "uppercase",
                    marginBottom: 8,
                  }}
                >
                  Senha
                </label>
                <div style={{ position: "relative" }}>
                  <input
                    className="login-input"
                    type={showPassword ? "text" : "password"}
                    placeholder="••••••••"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                    autoComplete="current-password"
                    style={{ paddingRight: 44 }}
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword((v) => !v)}
                    style={{
                      position: "absolute",
                      right: 14,
                      top: "50%",
                      transform: "translateY(-50%)",
                      background: "none",
                      border: "none",
                      cursor: "pointer",
                      color: "#525258",
                      display: "flex",
                      alignItems: "center",
                      padding: 0,
                    }}
                    tabIndex={-1}
                  >
                    <span
                      className="material-symbols-outlined"
                      style={{ fontSize: 18 }}
                    >
                      {showPassword ? "visibility_off" : "visibility"}
                    </span>
                  </button>
                </div>
              </div>

              {/* Error */}
              {error && (
                <div
                  className="anim-4"
                  style={{
                    marginBottom: 20,
                    padding: "12px 14px",
                    background: "rgba(220,38,38,0.08)",
                    border: "1px solid rgba(220,38,38,0.2)",
                    borderRadius: 10,
                    display: "flex",
                    alignItems: "center",
                    gap: 8,
                  }}
                >
                  <span
                    className="material-symbols-outlined"
                    style={{ fontSize: 16, color: "#ff6b6b", flexShrink: 0 }}
                  >
                    error
                  </span>
                  <span style={{ fontSize: 13, color: "#ff6b6b" }}>
                    {error}
                  </span>
                </div>
              )}

              {/* Submit */}
              <div className="anim-4">
                <button
                  type="submit"
                  className="btn-login"
                  disabled={loading}
                >
                  {loading && <span className="spinner" />}
                  {loading ? "Entrando..." : "Entrar no painel"}
                </button>
              </div>
            </form>

            {/* Footer */}
            <div
              className="anim-5"
              style={{
                marginTop: 40,
                paddingTop: 24,
                borderTop: "1px solid rgba(255,255,255,0.04)",
                display: "flex",
                alignItems: "center",
                gap: 6,
              }}
            >
              <span style={{ fontSize: 12, color: "#2d2d33" }}>
                Protegido por
              </span>
              <span
                style={{
                  fontSize: 12,
                  color: "#3a3a42",
                  fontWeight: 600,
                }}
              >
                NexoIA Security
              </span>
              <span className="material-symbols-outlined" style={{ fontSize: 13, color: "#2d2d33" }}>
                lock
              </span>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
