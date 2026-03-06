"""reset content_hash — nouvelle formule titre+employeur+ville (sans URL)

Les hashes existants sont calculés avec l'ancienne formule (titre+employeur+url).
On les remet à NULL pour qu'ils soient recalculés au prochain scrape.

Revision ID: 0005
Revises: 0004
Create Date: 2026-03-03 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("UPDATE offers SET content_hash = NULL")


def downgrade() -> None:
    pass  # Les anciens hashes ne peuvent pas être restaurés
