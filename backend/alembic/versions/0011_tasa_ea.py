"""tasa efectiva anual (E.A.) en tarjetas

Revision ID: 0011
Revises: 0010
Create Date: 2026-09-28
"""
import sqlalchemy as sa

from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Los extractos colombianos publican la tasa efectiva anual; guardamos ambas.
    op.add_column("tarjetas", sa.Column("tasa_interes_ea", sa.Numeric(8, 4), nullable=True))


def downgrade() -> None:
    op.drop_column("tarjetas", "tasa_interes_ea")
