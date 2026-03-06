"""add content_hash to offers

Revision ID: 0002
Revises: 0001
Create Date: 2026-03-02 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("offers", sa.Column("content_hash", sa.String(), nullable=True))
    op.create_index("ix_offers_content_hash", "offers", ["content_hash"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_offers_content_hash", table_name="offers")
    op.drop_column("offers", "content_hash")
