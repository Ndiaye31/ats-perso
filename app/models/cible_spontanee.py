import uuid
from datetime import datetime

from sqlalchemy import Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class CibleSpontanee(Base):
    __tablename__ = "cibles_spontanees"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    # Identification
    nom: Mapped[str] = mapped_column(nullable=False)           # "Mairie de Chessy"
    secteur: Mapped[str] = mapped_column(nullable=False)       # "mairies" | "education"
    type_organisation: Mapped[str | None] = mapped_column(nullable=True)  # "Mairie" | "Lycée"
    departement: Mapped[str | None] = mapped_column(nullable=True)        # "77"
    education_type: Mapped[str | None] = mapped_column(nullable=True)     # "lycee" | "college" | ...

    # Contact
    email: Mapped[str | None] = mapped_column(nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Candidature
    titre_poste: Mapped[str | None] = mapped_column(nullable=True)
    lm_texte: Mapped[str | None] = mapped_column(Text, nullable=True)
    cv_path: Mapped[str | None] = mapped_column(nullable=True)

    # Workflow : neuf → prêt → envoyé / erreur
    statut: Mapped[str] = mapped_column(nullable=False, default="neuf")
    erreur: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Timestamps
    date_scrape: Mapped[datetime | None] = mapped_column(nullable=True)
    date_envoi: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
