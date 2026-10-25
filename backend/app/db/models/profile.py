import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Profile(Base):
    __tablename__ = "profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("dataset_versions.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    engine_version: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    column_profiles: Mapped[list["ColumnProfile"]] = relationship(
        "ColumnProfile", back_populates="profile", cascade="all, delete-orphan"
    )


class ColumnProfile(Base):
    __tablename__ = "column_profiles"
    __table_args__ = (
        UniqueConstraint("profile_id", "position", name="uq_column_profiles_position"),
        UniqueConstraint("profile_id", "name", name="uq_column_profiles_name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    inferred_dtype: Mapped[str] = mapped_column(Text, nullable=False)
    semantic_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    semantic_desc: Mapped[str | None] = mapped_column(Text, nullable=True)
    semantic_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    null_count: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    null_pct: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    distinct_count: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    stats: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    missing_tokens: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list, nullable=False)
    pii_types: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list, nullable=False)
    is_pii: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    profile: Mapped["Profile"] = relationship("Profile", back_populates="column_profiles")
