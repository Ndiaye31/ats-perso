import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class CandidatureRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    offer_id: uuid.UUID
    statut: str
    mode_candidature: str
    lm_texte: str | None
    date_envoi: date | None
    email_contact: str | None
    created_at: datetime
    updated_at: datetime
