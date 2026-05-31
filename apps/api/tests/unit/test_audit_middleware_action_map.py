import pytest

from interface.http.middleware import resolve_audit_action


@pytest.mark.parametrize("method,path,expected_label,expected_resource", [
    ("POST", "/admin/auth/login", None, None),
    ("POST", "/admin/users", "Criou usuário", "user"),
    ("PUT", "/admin/users/abc-123", "Editou usuário", "user"),
    ("DELETE", "/admin/users/abc-123", "Excluiu usuário", "user"),
    ("POST", "/admin/users/abc-123/reset-password", "Resetou senha de usuário", "user"),
    ("PUT", "/admin/me/password", "Alterou própria senha", "user"),
    ("POST", "/admin/products", "Criou produto", "product"),
    ("DELETE", "/admin/products/abc-123", "Excluiu produto", "product"),
    ("POST", "/admin/followup/flows", "Criou flow de follow-up", "flow"),
    ("DELETE", "/admin/followup/flows/abc/steps/def", "Excluiu step do flow", "flow_step"),
    ("PUT", "/admin/settings", "Editou configurações", "settings"),
    ("POST", "/admin/api-tokens", "Criou token de API", "api_token"),
    ("DELETE", "/admin/api-tokens/abc-123", "Revogou token de API", "api_token"),
    ("POST", "/admin/profiles", "Criou perfil", "profile"),
    ("DELETE", "/admin/profiles/abc-123", "Excluiu perfil", "profile"),
    ("POST", "/admin/dlq/abc/requeue", "Reprocessou job DLQ", "dlq"),
    ("GET", "/admin/leads", None, None),
    ("POST", "/admin/search/test", None, None),
])
def test_resolve_audit_action(method, path, expected_label, expected_resource):
    result = resolve_audit_action(method, path)
    if expected_label is None:
        assert result is None
    else:
        assert result is not None
        label, resource_type = result
        assert label == expected_label
        assert resource_type == expected_resource
