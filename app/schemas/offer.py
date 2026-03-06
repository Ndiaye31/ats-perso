import uuid
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, model_validator


class OfferRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    company: str
    location: str | None
    url: str | None
    description: str | None
    status: str
    applied_at: date | None
    date_limite: str | None
    contact_email: str | None
    candidature_url: str | None
    score: int | None
    score_details: dict[str, Any] | None
    source_id: uuid.UUID | None
    source_name: str | None = None
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="wrap")
    @classmethod
    def set_source_name(cls, obj: Any, handler: Any) -> "OfferRead":
        result = handler(obj)
        if hasattr(obj, "source") and obj.source is not None:
            result.source_name = obj.source.name
        return result


class OfferTableRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    company: str
    location: str | None
    url: str | None
    status: str
    date_limite: str | None
    contact_email: str | None
    candidature_url: str | None
    score: int | None
    source_id: uuid.UUID | None
    source_name: str | None = None
    created_at: datetime

    @model_validator(mode="wrap")
    @classmethod
    def set_source_name(cls, obj: Any, handler: Any) -> "OfferTableRead":
        result = handler(obj)
        if hasattr(obj, "source") and obj.source is not None:
            result.source_name = obj.source.name
        return result


class OfferTableResponse(BaseModel):
    items: list[OfferTableRead]
    total: int
    limit: int
    offset: int
