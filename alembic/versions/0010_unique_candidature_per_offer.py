"""add unique partial index: one active candidature per offer + purge unapplyable offers

Revision ID: 0010
Revises: 0009
Create Date: 2026-03-09 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Supprimer les offres sans moyen de candidature (ni email, ni candidature_url)
    op.execute(
        "DELETE FROM offers "
        "WHERE contact_email IS NULL "
        "AND candidature_url IS NULL"
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_candidatures_offer_active "
        "ON candidatures (offer_id) "
        "WHERE statut != 'annulée'"
    )


def downgrade() -> None:
    op.drop_index("uq_candidatures_offer_active", table_name="candidatures")
