"""etiquetas y subetiquetas (autojerárquica) + etiqueta_id en transacciones

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-27
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "etiquetas",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("usuario_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False),
        sa.Column("nombre", sa.String(60), nullable=False),
        sa.Column("color", sa.String(20), nullable=True),
        sa.Column("padre_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("etiquetas.id", ondelete="CASCADE"), nullable=True),
        sa.Column("creada_en", postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_etiquetas_usuario", "etiquetas", ["usuario_id"])

    op.add_column(
        "transacciones",
        sa.Column(
            "etiqueta_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("etiquetas.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("transacciones", "etiqueta_id")
    op.drop_table("etiquetas")
