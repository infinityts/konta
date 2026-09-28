"""transferencias entre cuentas

Revision ID: 0022
Revises: 0021
Create Date: 2026-09-28

Mover dinero entre dos cuentas propias deja de registrarse como un gasto y un
ingreso del mismo monto (que ensuciaba reportes y flujo de caja): ahora hay un
tipo `transferencia` con cuenta de origen (`cuenta_id`) y de destino
(`cuenta_destino_id`).

Nota de downgrade: PostgreSQL no permite **quitar** un valor de un ENUM, así que
`transferencia` se queda en el tipo (inofensivo: sin la columna de destino no hay
forma de crear una transferencia válida).
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE tipo_transaccion ADD VALUE IF NOT EXISTS 'transferencia'")

    op.add_column(
        "transacciones",
        sa.Column("cuenta_destino_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_transacciones_cuenta_destino",
        "transacciones",
        "cuentas",
        ["cuenta_destino_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_transacciones_cuenta_destino_id", "transacciones", ["cuenta_destino_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_transacciones_cuenta_destino_id", table_name="transacciones")
    op.drop_constraint(
        "fk_transacciones_cuenta_destino", "transacciones", type_="foreignkey"
    )
    op.drop_column("transacciones", "cuenta_destino_id")
    # `transferencia` se queda en el ENUM: PostgreSQL no permite quitarlo.
