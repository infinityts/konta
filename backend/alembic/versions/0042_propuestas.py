"""propuestas del asistente (acciones que esperan confirmación)

Revision ID: 0042
Revises: 0041
Create Date: 2026-09-30

El asistente no ejecuta: propone. Aquí queda lo propuesto con sus datos ya resueltos, para que al
confirmar se ejecute exactamente lo que el usuario vio.
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0042"
down_revision = "0041"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "propuestas",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "usuario_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("usuarios.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tipo", sa.String(32), nullable=False),
        sa.Column("datos", sa.Text(), nullable=False),
        sa.Column("resumen", sa.Text(), nullable=False),
        sa.Column("estado", sa.String(16), nullable=False, server_default="pendiente"),
        sa.Column("resultado", sa.Text(), nullable=True),
        sa.Column(
            "creada_en", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
        sa.Column("resuelta_en", sa.TIMESTAMP(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("propuestas")
