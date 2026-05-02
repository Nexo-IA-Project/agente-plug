# tests/unit/interface/admin/test_documents_router.py
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient


def _make_app_with_mock_deps(mock_deps):
    from interface.http.deps.admin_deps import get_admin_deps
    from interface.http.routers.admin.documents import router

    app = FastAPI()
    app.dependency_overrides[get_admin_deps] = lambda: mock_deps
    app.include_router(router, prefix="/admin")
    return app


def _make_mock_deps(doc_list=None):
    deps = MagicMock()
    deps.listar = AsyncMock(return_value=doc_list or [])
    deps.ingerir = AsyncMock()
    deps.deletar = AsyncMock()
    deps.buscar = AsyncMock(return_value=[])
    return deps


def test_list_documents_returns_200():
    deps = _make_mock_deps()
    app = _make_app_with_mock_deps(deps)
    client = TestClient(app)
    # Provide a valid-looking Authorization header (content ignored via mock)
    response = client.get("/admin/documents", headers={"Authorization": "Bearer faketoken"})
    assert response.status_code == 200
    assert response.json() == []


def test_list_documents_calls_listar_use_case():
    from shared.domain.entities.knowledge_document import KnowledgeDocument

    doc = KnowledgeDocument(
        account_id=1,
        filename="test.pdf",
        mime_type="application/pdf",
        file_size_bytes=100,
        created_by="admin@test.com",
    )
    deps = _make_mock_deps(doc_list=[doc])
    app = _make_app_with_mock_deps(deps)
    client = TestClient(app)
    response = client.get("/admin/documents", headers={"Authorization": "Bearer faketoken"})
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["filename"] == "test.pdf"


def test_delete_document_returns_204():
    deps = _make_mock_deps()
    app = _make_app_with_mock_deps(deps)
    client = TestClient(app)
    response = client.delete(
        "/admin/documents/doc-1", headers={"Authorization": "Bearer faketoken"}
    )
    assert response.status_code == 204
