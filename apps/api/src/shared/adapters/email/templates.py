# apps/api/src/shared/adapters/email/templates.py
from __future__ import annotations


def welcome_email(name: str, email: str, temp_password: str) -> tuple[str, str]:
    subject = "Seu acesso ao NexoIA"
    body = f"""
<html>
  <body style="font-family: -apple-system, sans-serif; max-width: 560px; margin: 0 auto; padding: 32px 24px;">
    <h2 style="color:#111">Olá, {name}!</h2>
    <p>Seu acesso ao painel NexoIA foi criado. Use as credenciais abaixo para entrar:</p>
    <div style="background:#f5f5f5;border-radius:8px;padding:16px;margin:16px 0;">
      <p style="margin:4px 0"><strong>Email:</strong> {email}</p>
      <p style="margin:4px 0"><strong>Senha temporária:</strong> <code>{temp_password}</code></p>
    </div>
    <p>No primeiro login você será solicitado a definir uma nova senha.</p>
    <p style="color:#666;font-size:12px;margin-top:32px">Se você não esperava este email, ignore.</p>
  </body>
</html>
"""
    return subject, body


def password_reset_email(name: str, temp_password: str) -> tuple[str, str]:
    subject = "Sua senha foi resetada"
    body = f"""
<html>
  <body style="font-family: -apple-system, sans-serif; max-width: 560px; margin: 0 auto; padding: 32px 24px;">
    <h2 style="color:#111">Olá, {name}!</h2>
    <p>Um administrador resetou sua senha do NexoIA. Sua nova senha temporária:</p>
    <div style="background:#f5f5f5;border-radius:8px;padding:16px;margin:16px 0;">
      <p style="margin:4px 0"><strong>Senha temporária:</strong> <code>{temp_password}</code></p>
    </div>
    <p>Você precisará trocar esta senha no próximo login.</p>
    <p style="color:#666;font-size:12px;margin-top:32px">Se você não solicitou este reset, contate o administrador.</p>
  </body>
</html>
"""
    return subject, body
