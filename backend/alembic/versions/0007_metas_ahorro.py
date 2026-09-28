"""metas de ahorro y sus aportes

Revision ID: 0007
Revises: 0006
Create Date: 2026-09-27
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "metas_ahorro",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("usuario_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False),
        sa.Column("nombre", sa.String(120), nullable=False),
        sa.Column("monto_objetivo", sa.Numeric(14, 2), nullable=False),
        sa.Column("moneda", sa.String(3), sa.ForeignKey("monedas.codigo"), nullable=False, server_default=sa.text("'COP'")),
        sa.Column("fecha_limite", sa.Date(), nullable=True),
        sa.Column("notas", sa.Text(), nullable=True),
        sa.Column("creada_en", postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_metas_usuario", "metas_ahorro", ["usuario_id"])

    op.create_table(
        "aportes_meta",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("usuario_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False),
        sa.Column("meta_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("metas_ahorro.id", ondelete="CASCADE"), nullable=False),
        sa.Column("monto", sa.Numeric(14, 2), nullable=False),
        sa.Column("fecha", sa.Date(), nullable=False, server_default=sa.text("CURRENT_DATE")),
        sa.Column("notas", sa.String(255), nullable=True),
        sa.Column("creada_en", postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_aportes_usuario", "aportes_meta", ["usuario_id"])
    op.create_index("ix_aportes_meta", "aportes_meta", ["meta_id"])


def downgrade() -> None:
    op.drop_table("aportes_meta")
    op.drop_table("metas_ahorro")
