"""Architecture tests — ensure domain layer stays pure."""

from __future__ import annotations

import ast
from pathlib import Path

DOMAIN_DIR = Path(__file__).resolve().parents[3] / "src" / "shared" / "domain"

FORBIDDEN_IMPORTS = {
    "sqlalchemy",
    "redis",
    "openai",
    "fastapi",
    "httpx",
    "langgraph",
    "alembic",
    "pydantic_settings",
    "prometheus_client",
    "structlog",
}


def _iter_python_files(root: Path) -> list[Path]:
    return [p for p in root.rglob("*.py") if p.is_file()]


def _extract_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    return names


def test_domain_does_not_import_external_frameworks() -> None:
    offenders: list[str] = []
    for path in _iter_python_files(DOMAIN_DIR):
        imports = _extract_imports(path)
        bad = imports & FORBIDDEN_IMPORTS
        if bad:
            offenders.append(f"{path.relative_to(DOMAIN_DIR.parents[2])}: {sorted(bad)}")
    assert not offenders, "Domain layer must not import frameworks:\n" + "\n".join(offenders)


def test_domain_does_not_import_from_other_layers() -> None:
    offenders: list[str] = []
    for path in _iter_python_files(DOMAIN_DIR):
        full_imports = {
            line.split()[1]
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip().startswith(("import ", "from "))
        }
        for full in full_imports:
            if full.startswith("shared.") and not full.startswith("shared.domain"):
                offenders.append(f"{path}: {full}")
    assert not offenders, "Domain must only import from shared.domain.*:\n" + "\n".join(offenders)
