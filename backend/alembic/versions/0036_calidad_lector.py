"""calidad de la lectura por factura

Revision ID: 0036
Revises: 0035
Create Date: 2026-09-30

Dos datos para saber donde falla el lector: si hubo que corregir la factura y si salio bien
gracias a una plantilla aprendida del emisor.
"""
import sqlalchemy as sa

from alembic import op

revision = "0036"
down_revision = "0035"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "facturas", sa.Column("corregida_en", sa.TIMESTAMP(timezone=True), nullable=True)
    )
    op.add_column(
        "facturas",
        sa.Column(
            "leida_con_plantilla", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
    )


def downgrade() -> None:
    op.drop_column("facturas", "leida_con_plantilla")
    op.drop_column("facturas", "corregida_en")
