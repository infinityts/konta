"""almacenamiento medido por dia (MB-dia)

Revision ID: 0040
Revises: 0039
Create Date: 2026-09-30

Para poder cobrar el espacio con criterio: cada dia se suma lo que ocupan los archivos del
usuario al mes en curso. Con eso se calcula el promedio y lo que cuesta de verdad cada cliente.
"""
import sqlalchemy as sa

from alembic import op

revision = "0040"
down_revision = "0039"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "consumos_ia", sa.Column("archivos_dia", sa.Integer(), nullable=False, server_default="0")
    )
    op.add_column(
        "consumos_ia", sa.Column("mb_dia", sa.Numeric(14, 3), nullable=False, server_default="0")
    )
    op.add_column("consumos_ia", sa.Column("ultima_medicion", sa.Date(), nullable=True))
    op.add_column(
        "consumos_ia", sa.Column("dias_medidos", sa.Integer(), nullable=False, server_default="0")
    )


def downgrade() -> None:
    for columna in ("dias_medidos", "ultima_medicion", "mb_dia", "archivos_dia"):
        op.drop_column("consumos_ia", columna)
