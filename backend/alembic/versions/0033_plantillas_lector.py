"""plantillas por emisor: dónde está el total y la fecha

Revision ID: 0033
Revises: 0032
Create Date: 2026-09-30

No se puede ir a cada banco o establecimiento a pedirles un formato, pero la app sí puede
aprenderse el de cada uno. Aquí se guarda, por usuario y emisor, en qué etiqueta viene el
total y en cuál la fecha, para que la próxima factura del mismo emisor salga bien a la
primera. También se guarda el emisor detectado en cada factura.
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0033"
down_revision = "0032"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("facturas", sa.Column("emisor", sa.String(140), nullable=True))
    op.add_column("facturas", sa.Column("emisor_nombre", sa.String(140), nullable=True))

    op.create_table(
        "plantillas_lector",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "usuario_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("usuarios.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("emisor", sa.String(140), nullable=False),
        sa.Column("nombre", sa.String(140), nullable=False),
        sa.Column("campo_monto", sa.String(40), nullable=True),
        sa.Column("campo_fecha", sa.String(40), nullable=True),
        sa.Column("tipo_documento", sa.String(20), nullable=True),
        sa.Column("usos", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "creada_en", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
        sa.Column(
            "actualizada_en",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("usuario_id", "emisor", name="uq_plantillas_lector_emisor"),
    )


def downgrade() -> None:
    op.drop_table("plantillas_lector")
    op.drop_column("facturas", "emisor_nombre")
    op.drop_column("facturas", "emisor")
