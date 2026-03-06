import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import ForeignKey, JSON, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Offer(Base):
    __tablename__ = "offers"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(nullable=False)
    company: Mapped[str] = mapped_column(nullable=False)
    location: Mapped[str | None] = mapped_column(nullable=True)
    url: Mapped[str | None] = mapped_column(nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(nullable=False, default="new")
    applied_at: Mapped[date | None] = mapped_column(nullable=True)
    content_hash: Mapped[str | None] = mapped_column(unique=True, nullable=True, index=True)
    date_limite: Mapped[str | None] = mapped_column(nullable=True)
    contact_email: Mapped[str | None] = mapped_column(nullable=True)
    candidature_url: Mapped[str | None] = mapped_column(nullable=True)
    score: Mapped[int | None] = mapped_column(nullable=True)
    score_details: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sources.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now(), nullable=False
    )

    source: Mapped["Source | None"] = relationship("Source", lazy="select")  # type: ignore[name-defined]
