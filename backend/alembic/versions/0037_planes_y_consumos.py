"""planes, cuotas y consumo de IA

Revision ID: 0037
Revises: 0036
Create Date: 2026-09-30

Para poder vender lecturas de factura con IA sin regalar dinero: un catálogo de planes, el plan
de cada usuario, un saldo de lecturas compradas aparte y un libro de consumo por mes con los
tokens y el coste real.
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0037"
down_revision = "0036"
branch_labels = None
depends_on = None

PLANES = [
    # codigo, nombre, precio_mes, lecturas_ia, consultas_asistente, orden
    ("basico", "Básico", 6000, 10, 10, 1),
    ("personal", "Personal", 12000, 30, 40, 2),
    ("pro", "Pro", 29000, 100, 150, 3),
]


def upgrade() -> None:
    op.create_table(
        "planes",
        sa.Column("codigo", sa.String(24), primary_key=True),
        sa.Column("nombre", sa.String(60), nullable=False),
        sa.Column("precio_mes", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("lecturas_ia", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("consultas_asistente", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("orden", sa.Integer(), nullable=False, server_default="0"),
    )
    planes = sa.table(
        "planes",
        sa.column("codigo", sa.String),
        sa.column("nombre", sa.String),
        sa.column("precio_mes", sa.Numeric),
        sa.column("lecturas_ia", sa.Integer),
        sa.column("consultas_asistente", sa.Integer),
        sa.column("orden", sa.Integer),
    )
    op.bulk_insert(
        planes,
        [
            {
                "codigo": c,
                "nombre": n,
                "precio_mes": p,
                "lecturas_ia": lect,
                "consultas_asistente": q,
                "orden": o,
            }
            for c, n, p, lect, q, o in PLANES
        ],
    )

    op.add_column(
        "usuarios",
        sa.Column("plan_codigo", sa.String(24), nullable=False, server_default="basico"),
    )
    op.add_column(
        "usuarios",
        sa.Column("lecturas_extra", sa.Integer(), nullable=False, server_default="0"),
    )

    op.create_table(
        "consumos_ia",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "usuario_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("usuarios.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("periodo", sa.String(7), nullable=False),
        sa.Column("lecturas", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("consultas", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tokens_entrada", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tokens_salida", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("costo_usd", sa.Numeric(12, 6), nullable=False, server_default="0"),
        sa.Column(
            "actualizado_en",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("usuario_id", "periodo", name="uq_consumos_ia_periodo"),
    )


def downgrade() -> None:
    op.drop_table("consumos_ia")
    op.drop_column("usuarios", "lecturas_extra")
    op.drop_column("usuarios", "plan_codigo")
    op.drop_table("planes")
