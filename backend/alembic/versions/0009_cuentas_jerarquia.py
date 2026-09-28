"""cuentas con saldo inicial + jerarquía de categorías

Revision ID: 0009
Revises: 0008
Create Date: 2026-09-27
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cuentas",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("usuario_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False),
        sa.Column("nombre", sa.String(80), nullable=False),
        sa.Column("tipo", sa.String(20), nullable=False, server_default=sa.text("'efectivo'")),
        sa.Column("saldo_inicial", sa.Numeric(14, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("moneda", sa.String(3), sa.ForeignKey("monedas.codigo"), nullable=False, server_default=sa.text("'COP'")),
        sa.Column("activa", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("creada_en", postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_cuentas_usuario", "cuentas", ["usuario_id"])

    # Jerarquía de categorías (categoría -> subcategoría)
    op.add_column("categorias", sa.Column("padre_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_categorias_padre", "categorias", "categorias", ["padre_id"], ["id"], ondelete="CASCADE"
    )

    # Cada transacción puede pertenecer a una cuenta
    op.add_column("transacciones", sa.Column("cuenta_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_transacciones_cuenta", "transacciones", "cuentas", ["cuenta_id"], ["id"], ondelete="SET NULL"
    )
    op.create_index("ix_transacciones_cuenta", "transacciones", ["cuenta_id"])


def downgrade() -> None:
    op.drop_index("ix_transacciones_cuenta", table_name="transacciones")
    op.drop_constraint("fk_transacciones_cuenta", "transacciones", type_="foreignkey")
    op.drop_column("transacciones", "cuenta_id")

    op.drop_constraint("fk_categorias_padre", "categorias", type_="foreignkey")
    op.drop_column("categorias", "padre_id")

    op.drop_index("ix_cuentas_usuario", table_name="cuentas")
    op.drop_table("cuentas")
