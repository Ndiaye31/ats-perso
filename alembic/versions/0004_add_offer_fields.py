"""add date_limite and contact_email to offers

Revision ID: 0004
Revises: 0003
Create Date: 2026-03-03 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("offers", sa.Column("date_limite", sa.String(), nullable=True))
    op.add_column("offers", sa.Column("contact_email", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("offers", "contact_email")
    op.drop_column("offers", "date_limite")
