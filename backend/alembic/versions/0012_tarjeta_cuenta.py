"""cuenta asociada a la tarjeta de débito

Revision ID: 0012
Revises: 0011
Create Date: 2026-09-28
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Una tarjeta de débito es un instrumento de una cuenta, no un saldo aparte.
    op.add_column("tarjetas", sa.Column("cuenta_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_tarjetas_cuenta", "tarjetas", "cuentas", ["cuenta_id"], ["id"], ondelete="SET NULL"
    )


def downgrade() -> None:
    op.drop_constraint("fk_tarjetas_cuenta", "tarjetas", type_="foreignkey")
    op.drop_column("tarjetas", "cuenta_id")
