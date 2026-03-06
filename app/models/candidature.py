import uuid
from datetime import date, datetime

from sqlalchemy import ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Candidature(Base):
    __tablename__ = "candidatures"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    offer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("offers.id", ondelete="CASCADE"), nullable=False
    )
    statut: Mapped[str] = mapped_column(nullable=False, default="brouillon")
    mode_candidature: Mapped[str] = mapped_column(nullable=False, default="inconnu")
    lm_texte: Mapped[str | None] = mapped_column(Text, nullable=True)
    date_envoi: Mapped[date | None] = mapped_column(nullable=True)
    email_contact: Mapped[str | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now(), nullable=False
    )

    offer: Mapped["Offer"] = relationship("Offer", lazy="select")  # type: ignore[name-defined]
