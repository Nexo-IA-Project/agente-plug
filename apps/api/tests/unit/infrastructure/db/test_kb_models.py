def test_kb_models_importable():
    from shared.adapters.db.models import (
        AdminUserModel,
        KbUsageLogModel,
        KnowledgeChunkModel,
        KnowledgeDocumentModel,
    )

    assert KnowledgeDocumentModel.__tablename__ == "knowledge_documents"
    assert KnowledgeChunkModel.__tablename__ == "knowledge_chunks"
    assert KbUsageLogModel.__tablename__ == "kb_usage_logs"
    assert AdminUserModel.__tablename__ == "admin_users"


def test_knowledge_document_model_columns():
    from shared.adapters.db.models import KnowledgeDocumentModel

    cols = {c.name for c in KnowledgeDocumentModel.__table__.columns}
    assert "id" in cols
    assert "account_id" in cols
    assert "filename" in cols
    assert "status" in cols
    assert "chunk_count" in cols
    assert "tags" in cols
    assert "created_by" in cols
