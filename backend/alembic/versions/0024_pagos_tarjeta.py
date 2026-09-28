"""pagos de tarjeta de crédito

Revision ID: 0024
Revises: 0023
Create Date: 2026-09-28

Tabla nueva `pagos_tarjeta`: pagar la tarjeta baja el saldo de la cuenta **y** la
deuda. La deuda del extracto (`deudas_tarjeta`) es un **nivel** y los pagos un
**flujo**: la deuda vigente es el último extracto de cada moneda menos los pagos
posteriores a su fecha. Cada pago queda enlazado a su transacción (una
transferencia de la cuenta a la tarjeta: pagar una deuda propia no es un gasto).
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pagos_tarjeta",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "usuario_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("usuarios.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "tarjeta_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tarjetas.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "cuenta_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("cuentas.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "transaccion_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("transacciones.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("monto", sa.Numeric(14, 2), nullable=False),
        sa.Column(
            "moneda",
            sa.String(length=3),
            sa.ForeignKey("monedas.codigo"),
            nullable=False,
            server_default="COP",
        ),
        sa.Column("fecha", sa.Date(), nullable=False),
        sa.Column("notas", sa.String(length=255), nullable=True),
        sa.Column(
            "creada_en",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_pagos_tarjeta_usuario_id", "pagos_tarjeta", ["usuario_id"])
    op.create_index("ix_pagos_tarjeta_tarjeta_id", "pagos_tarjeta", ["tarjeta_id"])
    op.create_index("ix_pagos_tarjeta_cuenta_id", "pagos_tarjeta", ["cuenta_id"])
    op.create_index("ix_pagos_tarjeta_fecha", "pagos_tarjeta", ["fecha"])


def downgrade() -> None:
    for indice in (
        "ix_pagos_tarjeta_fecha",
        "ix_pagos_tarjeta_cuenta_id",
        "ix_pagos_tarjeta_tarjeta_id",
        "ix_pagos_tarjeta_usuario_id",
    ):
        op.drop_index(indice, table_name="pagos_tarjeta")
    op.drop_table("pagos_tarjeta")
