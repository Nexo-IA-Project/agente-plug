from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Permission:
    key: str  # "<module>.<action>"
    module: str  # agrupador p/ UI futura
    label: str  # rótulo PT-BR
    action: str  # view|create|edit|delete|manage|...


def _p(module: str, action: str, label: str) -> Permission:
    return Permission(key=f"{module}.{action}", module=module, label=label, action=action)


PERMISSION_CATALOG: list[Permission] = [
    _p("dashboard", "view", "Ver painel"),
    _p("kb", "view", "Ver base de conhecimento"),
    _p("kb", "create", "Enviar documento"),
    _p("kb", "delete", "Excluir documento"),
    _p("accounts", "view", "Ver contas"),
    _p("products", "view", "Ver produtos"),
    _p("products", "create", "Criar produto"),
    _p("products", "edit", "Editar produto"),
    _p("products", "delete", "Excluir produto"),
    _p("leads", "view", "Ver leads"),
    _p("leads", "export", "Exportar leads"),
    _p("onboarding", "view", "Ver onboarding"),
    _p("onboarding", "create", "Criar flow"),
    _p("onboarding", "edit", "Editar flow"),
    _p("onboarding", "delete", "Excluir flow"),
    _p("onboarding", "resolve_unmapped", "Resolver pendências"),
    _p("templates", "view", "Ver templates"),
    _p("templates", "create", "Criar template"),
    _p("templates", "delete", "Excluir template"),
    _p("users", "view", "Ver usuários"),
    _p("users", "manage", "Gerenciar usuários"),
    _p("profiles", "view", "Ver perfis"),
    _p("profiles", "manage", "Gerenciar perfis"),
    _p("settings", "view", "Ver configurações"),
    _p("settings", "edit_credentials", "Editar credenciais/integração"),
    _p("settings", "edit_smtp", "Editar SMTP"),
    _p("tokens", "view", "Ver tokens de API"),
    _p("tokens", "manage", "Gerenciar tokens de API"),
    _p("audit", "view", "Ver auditoria"),
]


def all_permission_keys() -> list[str]:
    return [p.key for p in PERMISSION_CATALOG]


# Permissões hoje "admin-only" (operador NÃO tem). Base p/ o seed do perfil Operador.
ADMIN_ONLY_KEYS: frozenset[str] = frozenset(
    {
        "users.manage",
        "profiles.view",
        "profiles.manage",
        "templates.delete",
        "kb.delete",
        "tokens.manage",
        "settings.edit_credentials",
        "settings.edit_smtp",
        "audit.view",
    }
)
