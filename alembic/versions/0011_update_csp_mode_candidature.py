"""Recatégorise les candidatures CSP de portail_tiers vers choisir-service-public

Revision ID: 0011
Revises: 0010
Create Date: 2026-03-18 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0011"
down_revision: Union[str, None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE candidatures
        SET mode_candidature = 'choisir-service-public'
        WHERE mode_candidature = 'portail_tiers'
          AND offer_id IN (
              SELECT id FROM offers
              WHERE candidature_url LIKE '%choisirleservicepublic.gouv.fr%'
          )
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE candidatures
        SET mode_candidature = 'portail_tiers'
        WHERE mode_candidature = 'choisir-service-public'
          AND offer_id IN (
              SELECT id FROM offers
              WHERE candidature_url LIKE '%choisirleservicepublic.gouv.fr%'
          )
        """
    )
