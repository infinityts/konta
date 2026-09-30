"""buzon de casos: documentos que el lector leyo mal

Revision ID: 0035
Revises: 0034
Create Date: 2026-09-30

Guarda el texto, lo que dijo el lector, lo que el usuario dejo al final y (solo si lo autoriza)
el archivo. De ahi sale una tarea del backlog y, al arreglarla, un test.
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0035"
down_revision = "0034"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "casos_lector",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "usuario_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("usuarios.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "factura_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("facturas.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("emisor", sa.String(140), nullable=True),
        sa.Column("emisor_nombre", sa.String(140), nullable=True),
        sa.Column("texto", sa.Text(), nullable=False),
        sa.Column("tipo_documento", sa.String(20), nullable=True),
        sa.Column("monto_leido", sa.Numeric(14, 2), nullable=True),
        sa.Column("fecha_leida", sa.Date(), nullable=True),
        sa.Column("monto_corregido", sa.Numeric(14, 2), nullable=True),
        sa.Column("fecha_corregida", sa.Date(), nullable=True),
        sa.Column("motivo", sa.String(300), nullable=True),
        sa.Column("archivo", sa.LargeBinary(), nullable=True),
        sa.Column("archivo_nombre", sa.String(200), nullable=True),
        sa.Column("archivo_tipo", sa.String(80), nullable=True),
        sa.Column("estado", sa.String(16), nullable=False, server_default="abierto"),
        sa.Column(
            "creado_en", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
        sa.Column("resuelto_en", sa.TIMESTAMP(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("casos_lector")
