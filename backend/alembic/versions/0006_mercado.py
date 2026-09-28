"""mercado: productos, precios por tienda y lista de compras

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-27
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "productos",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("usuario_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False),
        sa.Column("nombre", sa.String(120), nullable=False),
        sa.Column("unidad", sa.String(20), nullable=True),
        sa.Column("creada_en", postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_productos_usuario", "productos", ["usuario_id"])

    op.create_table(
        "precios_mercado",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("usuario_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False),
        sa.Column("producto_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("productos.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tienda", sa.String(80), nullable=True),
        sa.Column("precio", sa.Numeric(14, 2), nullable=False),
        sa.Column("moneda", sa.String(3), sa.ForeignKey("monedas.codigo"), nullable=False, server_default=sa.text("'COP'")),
        sa.Column("fecha", sa.Date(), nullable=False, server_default=sa.text("CURRENT_DATE")),
    )
    op.create_index("ix_precios_usuario", "precios_mercado", ["usuario_id"])
    op.create_index("ix_precios_producto", "precios_mercado", ["producto_id"])

    op.create_table(
        "lista_mercado",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("usuario_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False),
        sa.Column("producto_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("productos.id", ondelete="SET NULL"), nullable=True),
        sa.Column("nombre", sa.String(120), nullable=False),
        sa.Column("cantidad", sa.Numeric(10, 2), nullable=False, server_default=sa.text("1")),
        sa.Column("precio_estimado", sa.Numeric(14, 2), nullable=True),
        sa.Column("comprado", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("creada_en", postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_lista_usuario", "lista_mercado", ["usuario_id"])


def downgrade() -> None:
    op.drop_table("lista_mercado")
    op.drop_table("precios_mercado")
    op.drop_table("productos")
