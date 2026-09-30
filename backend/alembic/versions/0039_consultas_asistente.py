"""registro de consultas al asistente

Revision ID: 0039
Revises: 0038
Create Date: 2026-09-30
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0039"
down_revision = "0038"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "consultas_asistente",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "usuario_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("usuarios.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("pregunta", sa.Text(), nullable=False),
        sa.Column("herramientas", sa.Text(), nullable=True),
        sa.Column("tokens_entrada", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tokens_salida", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("costo_usd", sa.Numeric(12, 6), nullable=False, server_default="0"),
        sa.Column(
            "creada_en", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
    )


def downgrade() -> None:
    op.drop_table("consultas_asistente")
