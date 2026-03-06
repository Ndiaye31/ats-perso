"""add mode_candidature to candidatures

Revision ID: 0007
Revises: 0006
Create Date: 2026-03-03 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "candidatures",
        sa.Column("mode_candidature", sa.String(), nullable=False, server_default="inconnu"),
    )


def downgrade() -> None:
    op.drop_column("candidatures", "mode_candidature")
