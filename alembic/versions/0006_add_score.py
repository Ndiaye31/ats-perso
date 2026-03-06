"""add score and score_details to offers

Revision ID: 0006
Revises: 0005
Create Date: 2026-03-03 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("offers", sa.Column("score", sa.Integer(), nullable=True))
    op.add_column("offers", sa.Column("score_details", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("offers", "score_details")
    op.drop_column("offers", "score")
