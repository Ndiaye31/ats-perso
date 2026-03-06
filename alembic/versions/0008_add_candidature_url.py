"""add candidature_url to offers

Revision ID: 0008
Revises: 0007
Create Date: 2026-03-04
"""
from alembic import op
import sqlalchemy as sa

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("offers", sa.Column("candidature_url", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("offers", "candidature_url")
