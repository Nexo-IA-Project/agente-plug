from __future__ import annotations

from dataclasses import dataclass


@dataclass
class AdminDeps:
    account_id: int
    user_email: str
    user_role: str
    settings: object
    doc_repo: object
    ingerir: object
    listar: object
    deletar: object
    buscar: object


async def get_admin_deps():
    raise NotImplementedError("configure get_admin_deps in Task 11")
