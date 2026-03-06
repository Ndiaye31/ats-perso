"""add performance indexes for offers and candidatures

Revision ID: 0009
Revises: 0008
Create Date: 2026-03-05 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_offers_score_created_at",
        "offers",
        ["score", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_offers_source_created_at",
        "offers",
        ["source_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_offers_status",
        "offers",
        ["status"],
        unique=False,
    )
    op.create_index(
        "ix_candidatures_offer_statut_created_at",
        "candidatures",
        ["offer_id", "statut", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_candidatures_offer_statut_created_at", table_name="candidatures")
    op.drop_index("ix_offers_status", table_name="offers")
    op.drop_index("ix_offers_source_created_at", table_name="offers")
    op.drop_index("ix_offers_score_created_at", table_name="offers")
