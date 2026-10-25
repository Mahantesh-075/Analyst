import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, ENUM, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

proposal_source_enum = ENUM(
    "rule",
    "llm",
    "user",
    name="proposal_source",
    create_type=False,
)

proposal_status_enum = ENUM(
    "pending",
    "accepted",
    "rejected",
    "applied",
    "failed",
    name="proposal_status",
    create_type=False,
)

severity_level_enum = ENUM(
    "info",
    "low",
    "medium",
    "high",
    name="severity_level",
    create_type=False,
)


class CleaningProposal(Base):
    __tablename__ = "cleaning_proposals"
    __table_args__ = (
        UniqueConstraint("base_version_id", "order_index", name="uq_proposals_order"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    dataset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("datasets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    base_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("dataset_versions.id"), nullable=False, index=True
    )
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    op: Mapped[str] = mapped_column(Text, nullable=False)
    params: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    target_columns: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    impact_preview: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    severity: Mapped[str] = mapped_column(severity_level_enum, default="info", nullable=False)
    source: Mapped[str] = mapped_column(proposal_source_enum, nullable=False)  # 'rule' | 'llm' | 'user'
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(proposal_status_enum, default="pending", nullable=False)
    edited_params: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ValidationResult(Base):
    __tablename__ = "validation_results"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("dataset_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    failures: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
