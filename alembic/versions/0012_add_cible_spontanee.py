"""add cibles_spontanees table

Revision ID: 0012
Revises: 0011
Create Date: 2026-03-27 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0012"
down_revision: Union[str, None] = "0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "cibles_spontanees",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("nom", sa.String(), nullable=False),
        sa.Column("secteur", sa.String(), nullable=False),
        sa.Column("type_organisation", sa.String(), nullable=True),
        sa.Column("departement", sa.String(), nullable=True),
        sa.Column("education_type", sa.String(), nullable=True),
        sa.Column("email", sa.String(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("titre_poste", sa.String(), nullable=True),
        sa.Column("lm_texte", sa.Text(), nullable=True),
        sa.Column("cv_path", sa.String(), nullable=True),
        sa.Column("statut", sa.String(), nullable=False, server_default="neuf"),
        sa.Column("erreur", sa.Text(), nullable=True),
        sa.Column("date_scrape", sa.DateTime(), nullable=True),
        sa.Column("date_envoi", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_cibles_spontanees_secteur", "cibles_spontanees", ["secteur"])
    op.create_index("ix_cibles_spontanees_statut", "cibles_spontanees", ["statut"])


def downgrade() -> None:
    op.drop_index("ix_cibles_spontanees_statut", table_name="cibles_spontanees")
    op.drop_index("ix_cibles_spontanees_secteur", table_name="cibles_spontanees")
    op.drop_table("cibles_spontanees")
