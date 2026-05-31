from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, ClassVar

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
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
    legal_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    tax_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
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
    last_onboarding_agent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chatnexo_agents.id", ondelete="SET NULL"),
        nullable=True,
    )
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
    actor: Mapped[str] = mapped_column(String(120), nullable=False)
    user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    user_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(40), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(80))
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    geo_city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    geo_country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    geo_region: Mapped[str | None] = mapped_column(String(100), nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, default=dict, nullable=False
    )
    correlation_id: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=sa_text("NOW()"), nullable=False
    )
    __table_args__ = (
        Index("ix_audit_events_account_created", "account_id", "created_at"),
        Index("ix_audit_events_account_user", "account_id", "user_id"),
    )


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
    name: Mapped[str] = mapped_column(String(512), nullable=False)
    meta_template_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    category: Mapped[str] = mapped_column(String(32), nullable=False, default="UTILITY")
    language: Mapped[str] = mapped_column(String(16), nullable=False)
    components: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list, nullable=False)
    variables_schema: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    media_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    media_object_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    media_kind: Mapped[str | None] = mapped_column(String(16), nullable=True)
    media_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    media_size: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="PENDING")
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
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
        UniqueConstraint("account_id", "name", name="uq_meta_template_account_name"),
        Index("ix_meta_templates_status", "status"),
    )


class ProductModel(Base):
    __tablename__ = "products"
    __table_args__ = (
        UniqueConstraint("account_id", "hubla_id", name="uq_products_account_hubla"),
        Index("ix_products_account_id", "account_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    hubla_id: Mapped[str] = mapped_column(String(200), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=sa_text("NOW()"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=sa_text("NOW()"),
        onupdate=sa_text("NOW()"),
        nullable=False,
    )


class ProductHublaAliasModel(Base):
    __tablename__ = "product_hubla_aliases"
    __table_args__ = (
        UniqueConstraint("account_id", "hubla_id", name="uq_product_alias_account_hubla"),
        Index("ix_product_alias_account_hubla", "account_id", "hubla_id"),
        Index("ix_product_alias_product", "product_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )
    hubla_id: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=sa_text("NOW()"), nullable=False
    )


class AccessCaseModel(Base):
    __tablename__ = "access_cases"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False, index=True
    )
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
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False, index=True
    )
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


class KnowledgeDocumentModel(Base):
    __tablename__ = "knowledge_documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False
    )
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
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False
    )
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
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False
    )
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


class UserModel(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(200), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(200), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    avatar: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    must_change_password: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=sa_text("TRUE")
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa_text("TRUE"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=sa_text("NOW()"), nullable=False
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    profile_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True
    )

    __table_args__ = (UniqueConstraint("account_id", "email", name="uq_users_account_email"),)


class ProfileModel(Base):
    __tablename__ = "profiles"
    __table_args__ = (UniqueConstraint("account_id", "name", name="uq_profiles_account_name"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    is_system: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=sa_text("FALSE")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=sa_text("NOW()"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=sa_text("NOW()"),
        onupdate=sa_text("NOW()"),
        nullable=False,
    )


class ProfilePermissionModel(Base):
    __tablename__ = "profile_permissions"
    __table_args__ = (UniqueConstraint("profile_id", "permission_key", name="uq_profile_perm"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    permission_key: Mapped[str] = mapped_column(String(100), nullable=False)


class IdentityModel(Base):
    __tablename__ = "identities"
    __table_args__ = (UniqueConstraint("email", name="uq_identities_email"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email: Mapped[str] = mapped_column(String(200), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(200), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    avatar: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    must_change_password: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=sa_text("TRUE")
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa_text("TRUE"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=sa_text("NOW()"), nullable=False
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class MembershipModel(Base):
    __tablename__ = "memberships"
    __table_args__ = (
        UniqueConstraint("identity_id", "account_id", name="uq_membership_identity_account"),
        Index("ix_memberships_account_id", "account_id"),
        Index("ix_memberships_identity_id", "identity_id"),
        Index(
            "uq_membership_owner_per_account",
            "account_id",
            unique=True,
            postgresql_where=sa_text("is_owner"),
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    identity_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("identities.id", ondelete="CASCADE"), nullable=False
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    profile_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profiles.id"), nullable=True
    )
    is_owner: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa_text("FALSE"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa_text("TRUE"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=sa_text("NOW()"), nullable=False
    )


class PlatformConfigModel(Base):
    """Global platform config (singleton row). OpenAI key + SMTP, shared across tenants."""

    __tablename__ = "platform_config"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    singleton: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=sa_text("TRUE"), unique=True
    )
    openai_api_key: Mapped[str | None] = mapped_column(Text, nullable=True)  # Fernet
    smtp_host: Mapped[str | None] = mapped_column(String(255), nullable=True)
    smtp_port: Mapped[int | None] = mapped_column(Integer, nullable=True)
    smtp_use_tls: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=sa_text("TRUE")
    )
    smtp_username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    smtp_encrypted_password: Mapped[str | None] = mapped_column(Text, nullable=True)  # Fernet
    smtp_from_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    smtp_from_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=sa_text("NOW()"),
        onupdate=sa_text("NOW()"),
        nullable=False,
    )


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


class JobQueueModel(Base):
    """Persistent job queue — rows are deleted on dequeue (SELECT FOR UPDATE SKIP LOCKED)."""

    __tablename__ = "job_queue"

    id: Mapped[uuid.UUID] = _pk()
    kind: Mapped[str] = mapped_column(String(80), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    attempt: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    last_error: Mapped[str | None] = mapped_column(String, nullable=True)
    priority: Mapped[int] = mapped_column(Integer, default=20, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=sa_text("NOW()"), nullable=False
    )
    __table_args__ = (
        Index(
            "ix_job_queue_dequeue",
            "priority",
            "created_at",
        ),
    )


class JobDlqModel(Base):
    """Dead-letter queue — jobs that exhausted all retry attempts."""

    __tablename__ = "job_dlq"

    id: Mapped[uuid.UUID] = _pk()
    kind: Mapped[str] = mapped_column(String(80), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False)
    last_error: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=sa_text("NOW()"), nullable=False
    )


class ApiTokenModel(Base):
    __tablename__ = "api_tokens"
    id: Mapped[uuid.UUID] = _pk()
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    token_prefix: Mapped[str | None] = mapped_column(String(12), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=sa_text("NOW()"), nullable=False
    )
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")


class OnboardingFlowModel(Base):
    __tablename__ = "onboarding_flows"
    id: Mapped[uuid.UUID] = _pk()
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    trigger_event_type: Mapped[str] = mapped_column(
        String(80),
        nullable=False,
        default="subscription.activated",
        server_default="subscription.activated",
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=sa_text("NOW()"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=sa_text("NOW()"),
        onupdate=sa_text("NOW()"),
        nullable=False,
    )


class OnboardingStepModel(Base):
    __tablename__ = "onboarding_steps"
    id: Mapped[uuid.UUID] = _pk()
    flow_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("onboarding_flows.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    delay_from_previous_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    meta_template_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    template_variables: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    message_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=sa_text("NOW()"), nullable=False
    )
    __table_args__ = (Index("ix_onboarding_steps_flow_position", "flow_id", "position"),)


class OnboardingEnrollmentModel(Base):
    __tablename__ = "onboarding_enrollments"
    id: Mapped[uuid.UUID] = _pk()
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False, index=True
    )
    flow_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("onboarding_flows.id", ondelete="SET NULL"),
        nullable=True,
    )
    contact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contacts.id"), nullable=False
    )
    conversation_id: Mapped[str] = mapped_column(String(200), nullable=False)
    contact_phone: Mapped[str] = mapped_column(String(30), nullable=False)
    purchase_id: Mapped[str] = mapped_column(String(200), nullable=False)
    customer_name: Mapped[str] = mapped_column(String(200), nullable=False)
    product_name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=sa_text("NOW()"), nullable=False
    )


class OnboardingEnrollmentStepModel(Base):
    __tablename__ = "onboarding_enrollment_steps"
    id: Mapped[uuid.UUID] = _pk()
    enrollment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("onboarding_enrollments.id"), nullable=False, index=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    delay_from_previous_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    meta_template_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    template_variables: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    message_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    scheduled_job_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    flow_step_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class HublaEventModel(Base):
    __tablename__ = "hubla_events"
    __table_args__ = (
        Index("ix_hubla_events_account_type", "account_id", "event_type"),
        Index("ix_hubla_events_subscription", "account_id", "hubla_subscription_id"),
        Index("ix_hubla_events_contact", "contact_id"),  # PR4 review fix
    )

    id: Mapped[uuid.UUID] = _pk()
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    hubla_subscription_id: Mapped[str] = mapped_column(String(100), nullable=False)
    hubla_product_id: Mapped[str] = mapped_column(
        String(100), nullable=False, default="", server_default=""
    )
    product_name: Mapped[str] = mapped_column(
        String(300), nullable=False, default="", server_default=""
    )
    payer_phone: Mapped[str] = mapped_column(
        String(30), nullable=False, default="", server_default=""
    )
    payer_email: Mapped[str] = mapped_column(
        String(200), nullable=False, default="", server_default=""
    )
    payer_name: Mapped[str] = mapped_column(
        String(200), nullable=False, default="", server_default=""
    )
    contact_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contacts.id", ondelete="SET NULL"), nullable=True
    )
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class LeadModel(Base):
    __tablename__ = "leads"
    __table_args__ = (
        UniqueConstraint(
            "account_id", "hubla_subscription_id", name="uq_leads_account_subscription"
        ),
        Index("ix_leads_account_phone", "account_id", "payer_phone"),
        Index("ix_leads_account_status", "account_id", "subscription_status"),
        Index("ix_leads_account_activated", "account_id", "activated_at"),
        Index("ix_leads_account_utm_source", "account_id", "utm_source"),  # PR4 review fix
        Index(
            "ix_leads_account_unmatched",
            "account_id",
            postgresql_where=sa_text("product_unmatched"),
        ),
    )

    id: Mapped[uuid.UUID] = _pk()
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
    )
    hubla_subscription_id: Mapped[str] = mapped_column(String(100), nullable=False)
    contact_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contacts.id", ondelete="SET NULL"), nullable=True
    )
    payer_phone: Mapped[str] = mapped_column(
        String(30), nullable=False, default="", server_default=""
    )
    payer_name: Mapped[str] = mapped_column(
        String(200), nullable=False, default="", server_default=""
    )
    payer_email: Mapped[str] = mapped_column(
        String(200), nullable=False, default="", server_default=""
    )
    payer_document: Mapped[str | None] = mapped_column(String(20), nullable=True)
    hubla_product_id: Mapped[str] = mapped_column(
        String(100), nullable=False, default="", server_default=""
    )
    product_unmatched: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    product_name: Mapped[str] = mapped_column(
        String(300), nullable=False, default="", server_default=""
    )
    offer_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    offer_name: Mapped[str | None] = mapped_column(String(300), nullable=True)
    amount_total_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    amount_subtotal_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    payment_method: Mapped[str | None] = mapped_column(String(50), nullable=True)
    subscription_status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="unknown", server_default="unknown"
    )
    utm_source: Mapped[str | None] = mapped_column(String(200), nullable=True)
    utm_medium: Mapped[str | None] = mapped_column(String(200), nullable=True)
    utm_campaign: Mapped[str | None] = mapped_column(String(500), nullable=True)
    utm_content: Mapped[str | None] = mapped_column(String(500), nullable=True)
    utm_term: Mapped[str | None] = mapped_column(String(200), nullable=True)
    session_ip: Mapped[str | None] = mapped_column(String(50), nullable=True)
    session_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    fbp: Mapped[str | None] = mapped_column(String(100), nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_event_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_event_type: Mapped[str] = mapped_column(
        String(80), nullable=False, default="", server_default=""
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ChatNexoAgentModel(Base):
    __tablename__ = "chatnexo_agents"
    __table_args__ = (
        UniqueConstraint("account_id", "name", name="uq_chatnexo_agents_account_name"),
    )
    id: Mapped[uuid.UUID] = _pk()
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    api_key_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=sa_text("NOW()"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=sa_text("NOW()"),
        onupdate=sa_text("NOW()"),
        nullable=False,
    )


class MetaTemplateMediaModel(Base):
    """Storage de bytes de mídia (imagem/vídeo/documento) usada em templates Meta.

    BYTEA + dedup por sha256. Servido publicamente via GET /public/media/{id}.
    """

    __tablename__ = "meta_template_media"
    __table_args__ = (
        UniqueConstraint("account_id", "sha256", name="uq_meta_template_media_account_sha"),
        CheckConstraint(
            "kind IN ('IMAGE', 'VIDEO', 'DOCUMENT')",
            name="ck_meta_template_media_kind",
        ),
    )

    id: Mapped[uuid.UUID] = _pk()
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    mime: Mapped[str] = mapped_column(String(128), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=sa_text("NOW()"), nullable=False
    )
