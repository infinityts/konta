"""los compromisos recurrentes llevan cuenta (y el ingreso se enlaza)

Revision ID: 0023
Revises: 0022
Create Date: 2026-09-28

Las pólizas ya guardaban de qué cuenta sale el dinero, pero las **suscripciones**
(los gastos recurrentes) y los **ingresos recurrentes** no: cada movimiento que
generaba el job quedaba sin cuenta, aparecía como «movimiento sin cuenta» y **no
movía ningún saldo**. Eso hacía que «no volver a registrarlo mes a mes» dejara las
cuentas mal.

Se añade también `transacciones.ingreso_recurrente_id`, el enlace simétrico al de
`suscripcion_id`, para que el listado pueda marcar los ingresos que vienen de un
compromiso.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for tabla in ("suscripciones", "ingresos_recurrentes"):
        op.add_column(
            tabla,
            sa.Column("cuenta_id", postgresql.UUID(as_uuid=True), nullable=True),
        )
        op.create_foreign_key(
            f"fk_{tabla}_cuenta", tabla, "cuentas", ["cuenta_id"], ["id"],
            ondelete="SET NULL",
        )
        op.create_index(f"ix_{tabla}_cuenta_id", tabla, ["cuenta_id"])

    op.add_column(
        "transacciones",
        sa.Column("ingreso_recurrente_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_transacciones_ingreso_recurrente",
        "transacciones",
        "ingresos_recurrentes",
        ["ingreso_recurrente_id"],
        ["id"],
        ondelete="SET NULL",
    )
    # Sin índice: igual que `suscripcion_id`, no se consulta por aquí


def downgrade() -> None:
    op.drop_constraint(
        "fk_transacciones_ingreso_recurrente", "transacciones", type_="foreignkey"
    )
    op.drop_column("transacciones", "ingreso_recurrente_id")

    for tabla in ("ingresos_recurrentes", "suscripciones"):
        op.drop_index(f"ix_{tabla}_cuenta_id", table_name=tabla)
        op.drop_constraint(f"fk_{tabla}_cuenta", tabla, type_="foreignkey")
        op.drop_column(tabla, "cuenta_id")
