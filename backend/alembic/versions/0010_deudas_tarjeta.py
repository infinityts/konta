"""deuda de tarjeta por moneda

Revision ID: 0010
Revises: 0009
Create Date: 2026-09-28
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "deudas_tarjeta",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("usuario_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tarjeta_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tarjetas.id", ondelete="CASCADE"), nullable=False),
        sa.Column("moneda", sa.String(3), sa.ForeignKey("monedas.codigo"), nullable=False, server_default=sa.text("'COP'")),
        sa.Column("monto", sa.Numeric(14, 2), nullable=False),
        sa.Column("fecha", sa.Date(), nullable=False, server_default=sa.text("CURRENT_DATE")),
        sa.Column("notas", sa.String(255), nullable=True),
        sa.Column("creada_en", postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_deudas_usuario", "deudas_tarjeta", ["usuario_id"])
    op.create_index("ix_deudas_tarjeta", "deudas_tarjeta", ["tarjeta_id"])


def downgrade() -> None:
    op.drop_table("deudas_tarjeta")
