"""facturas (PDF) con datos extraídos

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-27
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "facturas",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("usuario_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False),
        sa.Column("nombre_archivo", sa.String(255), nullable=False),
        sa.Column("texto_extraido", sa.Text(), nullable=True),
        sa.Column("monto_detectado", sa.Numeric(14, 2), nullable=True),
        sa.Column("fecha_detectada", sa.Date(), nullable=True),
        sa.Column("transaccion_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("transacciones.id", ondelete="SET NULL"), nullable=True),
        sa.Column("creada_en", postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_facturas_usuario", "facturas", ["usuario_id"])


def downgrade() -> None:
    op.drop_table("facturas")
