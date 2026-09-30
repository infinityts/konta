"""pagos: planes y paquetes de lecturas

Revision ID: 0041
Revises: 0040
Create Date: 2026-09-30

El nucleo del cobro, sin depender de la pasarela: la orden con su referencia (llave de
idempotencia), el estado, y la marca de aplicado que impide acreditar dos veces el mismo pago.
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0041"
down_revision = "0040"
branch_labels = None
depends_on = None

# codigo, nombre, lecturas, precio (provisional: se ajusta con la medicion del mes)
PAQUETES = [
    ("lecturas10", "10 lecturas con IA", 10, 3000),
    ("lecturas50", "50 lecturas con IA", 50, 12000),
]


def upgrade() -> None:
    op.create_table(
        "paquetes_lecturas",
        sa.Column("codigo", sa.String(24), primary_key=True),
        sa.Column("nombre", sa.String(60), nullable=False),
        sa.Column("lecturas", sa.Integer(), nullable=False),
        sa.Column("precio", sa.Numeric(12, 2), nullable=False),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("orden", sa.Integer(), nullable=False, server_default="0"),
    )
    paquetes = sa.table(
        "paquetes_lecturas",
        sa.column("codigo", sa.String),
        sa.column("nombre", sa.String),
        sa.column("lecturas", sa.Integer),
        sa.column("precio", sa.Numeric),
        sa.column("orden", sa.Integer),
    )
    op.bulk_insert(
        paquetes,
        [
            {"codigo": codigo, "nombre": nombre, "lecturas": lecturas, "precio": precio, "orden": i}
            for i, (codigo, nombre, lecturas, precio) in enumerate(PAQUETES, start=1)
        ],
    )

    op.create_table(
        "pagos",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "usuario_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("usuarios.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("referencia", sa.String(64), nullable=False, unique=True),
        sa.Column("tipo", sa.String(16), nullable=False),
        sa.Column("codigo", sa.String(24), nullable=False),
        sa.Column("monto", sa.Numeric(12, 2), nullable=False),
        sa.Column("moneda", sa.String(3), nullable=False, server_default="COP"),
        sa.Column("estado", sa.String(16), nullable=False, server_default="pendiente"),
        sa.Column("pasarela", sa.String(24), nullable=False, server_default="simulada"),
        sa.Column("id_externo", sa.String(120), nullable=True),
        sa.Column("aplicado", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("detalle", sa.Text(), nullable=True),
        sa.Column(
            "creado_en", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
        sa.Column("pagado_en", sa.TIMESTAMP(timezone=True), nullable=True),
    )



def downgrade() -> None:
    op.drop_table("pagos")
    op.drop_table("paquetes_lecturas")
