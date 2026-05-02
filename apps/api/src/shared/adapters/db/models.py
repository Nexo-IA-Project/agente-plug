from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, ClassVar

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    UniqueConstraint,
)
from sqlalchemy import (
    text as sa_text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    type_annotation_map: ClassVar[dict] = {dict[str, Any]: JSONB, list[str]: JSONB}


def _pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


class AccountModel(Base):
    __tablename__ = "accounts"
    id: Mapped[uuid.UUID] = _pk()
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    settings: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=sa_text("NOW()"), nullable=False
    )


class ContactModel(Base):
    __tablename__ = "contacts"
    id: Mapped[uuid.UUID] = _pk()
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False, index=True
    )
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str | None] = mapped_column(String(200))
    email: Mapped[str | None] = mapped_column(String(200))
    long_term_facts: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=sa_text("NOW()"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=sa_text("NOW()"),
        onupdate=sa_text("NOW()"),
        nullable=False,
    )
    __table_args__ = (UniqueConstraint("account_id", "phone", name="uq_contacts_account_phone"),)


class ConversationModel(Base):
    __tablename__ = "conversations"
    id: Mapped[uuid.UUID] = _pk()
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False, index=True
    )
    contact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contacts.id"), nullable=False, index=True
    )
    chatnexo_conversation_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    last_activity_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    window_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    handoff_reason: Mapped[str | None] = mapped_column(String(100))
    idle_state: Mapped[str] = mapped_column(String(20), default="none", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=sa_text("NOW()"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=sa_text("NOW()"),
        onupdate=sa_text("NOW()"),
        nullable=False,
    )
    __table_args__ = (
        UniqueConstraint(
            "account_id", "chatnexo_conversation_id", name="uq_conversations_account_chatnexo"
        ),
    )


class MessageModel(Base):
    __tablename__ = "messages"
    id: Mapped[uuid.UUID] = _pk()
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=False
    )
    direction: Mapped[str] = mapped_column(String(10), nullable=False)
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(String, nullable=False)
    media_urls: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    classification_hint: Mapped[str | None] = mapped_column(String(50))
    correlation_id: Mapped[str | None] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=sa_text("NOW()"), nullable=False
    )
    __table_args__ = (Index("ix_messages_conv_created", "conversation_id", "created_at"),)


class WebhookEventModel(Base):
    __tablename__ = "webhook_events"
    id: Mapped[uuid.UUID] = _pk()
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    external_id: Mapped[str] = mapped_column(String(200), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    correlation_id: Mapped[str | None] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=sa_text("NOW()"), nullable=False
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        UniqueConstraint("source", "external_id", name="uq_webhook_events_source_external"),
    )


class ScheduledJobModel(Base):
    __tablename__ = "scheduled_jobs"
    id: Mapped[uuid.UUID] = _pk()
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False
    )
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id")
    )
    job_type: Mapped[str] = mapped_column(String(40), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    correlation_id: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=sa_text("NOW()"), nullable=False
    )
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        Index(
            "ix_scheduled_jobs_pending",
            "status",
            "run_at",
            postgresql_where=sa_text("status = 'pending'"),
        ),
    )


class CapabilityExecutionModel(Base):
    __tablename__ = "capability_executions"
    id: Mapped[uuid.UUID] = _pk()
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=False
    )
    capability_name: Mapped[str] = mapped_column(String(40), nullable=False)
    intent_confidence: Mapped[float] = mapped_column(nullable=False)
    tools_called: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list, nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    outcome: Mapped[str] = mapped_column(String(20), nullable=False)
    correlation_id: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=sa_text("NOW()"), nullable=False
    )


class AuditEventModel(Base):
    __tablename__ = "audit_events"
    id: Mapped[uuid.UUID] = _pk()
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False
    )
    actor: Mapped[str] = mapped_column(String(20), nullable=False)
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(40), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(80))
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, default=dict, nullable=False
    )
    correlation_id: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=sa_text("NOW()"), nullable=False
    )
    __table_args__ = (Index("ix_audit_events_account_created", "account_id", "created_at"),)


class IntegrationConfigModel(Base):
    __tablename__ = "integration_configs"
    id: Mapped[uuid.UUID] = _pk()
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False
    )
    integration_type: Mapped[str] = mapped_column(String(30), nullable=False)
    credentials_encrypted: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=sa_text("NOW()"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=sa_text("NOW()"),
        onupdate=sa_text("NOW()"),
        nullable=False,
    )


class MetaTemplateModel(Base):
    __tablename__ = "meta_templates"
    id: Mapped[uuid.UUID] = _pk()
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    meta_template_id: Mapped[str] = mapped_column(String(100), nullable=False)
    language: Mapped[str] = mapped_column(String(10), nullable=False)
    variables_schema: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    approved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AccessCaseModel(Base):
    __tablename__ = "access_cases"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    account_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    contact_id: Mapped[str] = mapped_column(String, nullable=False)
    conversation_id: Mapped[str] = mapped_column(String, nullable=False)
    purchase_id: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    product_name: Mapped[str] = mapped_column(String, nullable=False)
    access_link: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    access_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    scheduled_d1_job_id: Mapped[str | None] = mapped_column(String, nullable=True)
    student_cpf: Mapped[str | None] = mapped_column(String, nullable=True)
    search_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=sa_text("NOW()"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=sa_text("NOW()"),
        onupdate=sa_text("NOW()"),
        nullable=False,
    )

    __table_args__ = (Index("idx_access_cases_account_contact", "account_id", "contact_id"),)


class RefundCaseModel(Base):
    __tablename__ = "refund_cases"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    account_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    contact_id: Mapped[str] = mapped_column(String, nullable=False)
    conversation_id: Mapped[str] = mapped_column(String, nullable=False)
    purchase_id: Mapped[str | None] = mapped_column(String, nullable=True)
    product_name: Mapped[str | None] = mapped_column(String, nullable=True)
    student_email: Mapped[str] = mapped_column(String, nullable=False)
    student_cpf: Mapped[str | None] = mapped_column(String, nullable=True)
    refund_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    days_since_purchase: Mapped[int | None] = mapped_column(Integer, nullable=True)
    within_deadline: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    is_duplicate_purchase: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    offers_made: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    offer_accepted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    refund_processed_this_turn: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="collecting")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=sa_text("NOW()"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=sa_text("NOW()"),
        onupdate=sa_text("NOW()"),
        nullable=False,
    )

    __table_args__ = (Index("idx_refund_cases_account_contact", "account_id", "contact_id"),)


class LojaExpressCaseModel(Base):
    __tablename__ = "loja_express_cases"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    account_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    contact_id: Mapped[str] = mapped_column(String, nullable=False)
    conversation_id: Mapped[str] = mapped_column(String, nullable=False)
    purchase_id: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    product_name: Mapped[str] = mapped_column(String, nullable=False)
    student_email: Mapped[str] = mapped_column(String, nullable=False)
    form_submitted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    loja_entregue: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="aguardando_formulario")
    scheduled_job_d1_id: Mapped[str | None] = mapped_column(String, nullable=True)
    scheduled_job_d3_id: Mapped[str | None] = mapped_column(String, nullable=True)
    scheduled_job_d5_id: Mapped[str | None] = mapped_column(String, nullable=True)
    scheduled_job_d7_id: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=sa_text("NOW()"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=sa_text("NOW()"),
        onupdate=sa_text("NOW()"),
        nullable=False,
    )

    __table_args__ = (Index("idx_loja_express_cases_account_contact", "account_id", "contact_id"),)


class KnowledgeDocumentModel(Base):
    __tablename__ = "knowledge_documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    account_id: Mapped[int] = mapped_column(Integer, nullable=False)
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tags: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    error_message: Mapped[str | None] = mapped_column(String, nullable=True)
    created_by: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=sa_text("NOW()"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=sa_text("NOW()"),
        onupdate=sa_text("NOW()"),
        nullable=False,
    )

    __table_args__ = (Index("idx_knowledge_documents_account", "account_id"),)


class KnowledgeChunkModel(Base):
    __tablename__ = "knowledge_chunks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id: Mapped[str] = mapped_column(String(36), nullable=False)
    account_id: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(String, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False)
    embedding: Mapped[list] = mapped_column(Vector(1536), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=sa_text("NOW()"), nullable=False
    )

    __table_args__ = (
        Index("idx_knowledge_chunks_document", "document_id"),
        Index("idx_knowledge_chunks_account", "account_id"),
    )


class KbUsageLogModel(Base):
    __tablename__ = "kb_usage_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    account_id: Mapped[int] = mapped_column(Integer, nullable=False)
    query: Mapped[str] = mapped_column(String, nullable=False)
    result_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=sa_text("NOW()"), nullable=False
    )

    __table_args__ = (Index("idx_kb_usage_logs_account", "account_id"),)


class AdminUserModel(Base):
    __tablename__ = "admin_users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    account_id: Mapped[int] = mapped_column(Integer, nullable=False)
    email: Mapped[str] = mapped_column(String(200), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(200), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="viewer")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=sa_text("NOW()"), nullable=False
    )

    __table_args__ = (UniqueConstraint("account_id", "email", name="uq_admin_users_account_email"),)


class ConversationMessageModel(Base):
    """Stores the full OpenAI message list for a thread (used by the new agent loop)."""

    __tablename__ = "conversation_messages"

    thread_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    messages: Mapped[list[Any]] = mapped_column(JSONB, default=list, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=sa_text("NOW()"),
        onupdate=sa_text("NOW()"),
        nullable=False,
    )
