"""ingresos recurrentes (diario/semanal/mensual)

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-27
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

periodicidad_ingreso = postgresql.ENUM(
    "diario", "semanal", "mensual", name="periodicidad_ingreso", create_type=False
)


def upgrade() -> None:
    periodicidad_ingreso.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "ingresos_recurrentes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("usuario_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False),
        sa.Column("nombre", sa.String(120), nullable=False),
        sa.Column("monto", sa.Numeric(14, 2), nullable=False),
        sa.Column("moneda", sa.String(3), sa.ForeignKey("monedas.codigo"), nullable=False, server_default=sa.text("'COP'")),
        sa.Column("periodicidad", periodicidad_ingreso, nullable=False),
        sa.Column("dia", sa.Integer(), nullable=True),
        sa.Column("proxima_ejecucion", sa.Date(), nullable=False),
        sa.Column("categoria_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("categorias.id", ondelete="SET NULL"), nullable=True),
        sa.Column("activa", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("creada_en", postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_ingresos_recurrentes_usuario", "ingresos_recurrentes", ["usuario_id"])
    op.create_index("ix_ingresos_recurrentes_proxima", "ingresos_recurrentes", ["proxima_ejecucion"])


def downgrade() -> None:
    op.drop_table("ingresos_recurrentes")
    periodicidad_ingreso.drop(op.get_bind(), checkfirst=True)
