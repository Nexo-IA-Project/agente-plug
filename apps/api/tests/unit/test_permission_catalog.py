import re

from shared.domain.permissions.catalog import PERMISSION_CATALOG, all_permission_keys


def test_keys_are_unique_and_well_formed():
    keys = [p.key for p in PERMISSION_CATALOG]
    assert len(keys) == len(set(keys)), "chaves duplicadas no catálogo"
    for k in keys:
        assert re.fullmatch(r"[a-z_]+(\.[a-z_]+)+", k), f"chave mal formada: {k}"


def test_all_permission_keys_helper_matches_catalog():
    assert set(all_permission_keys()) == {p.key for p in PERMISSION_CATALOG}


def test_has_core_modules():
    modules = {p.module for p in PERMISSION_CATALOG}
    for m in ["dashboard", "products", "leads", "onboarding", "users", "settings"]:
        assert m in modules
