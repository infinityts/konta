"""impuestos de la factura (iva, descuento, bloque tributario) y marca de cada línea

Revision ID: 0029
Revises: 0028
Create Date: 2026-09-29

La factura electrónica trae su bloque tributario (IVA por tarifa, ICO, descuento). Se
guarda el total de impuestos, el IVA (sin el ICO), el descuento y el desglose completo en
JSON, para poder mostrarlo en el reporte y en el detalle de una compra.

Además, cada línea de la factura queda marcada con su tratamiento (`gravado`, `exento` o
`excluido`), que es lo que permite decir «el 36 % de tu mercado no paga IVA».
"""
import sqlalchemy as sa

from alembic import op

revision = "0029"
down_revision = "0028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("facturas", sa.Column("impuestos_total", sa.Numeric(14, 2), nullable=True))
    op.add_column("facturas", sa.Column("iva_valor", sa.Numeric(14, 2), nullable=True))
    op.add_column("facturas", sa.Column("descuento", sa.Numeric(14, 2), nullable=True))
    op.add_column("facturas", sa.Column("impuestos_detalle", sa.Text(), nullable=True))
    op.add_column("factura_lineas", sa.Column("iva_tipo", sa.String(10), nullable=True))


def downgrade() -> None:
    op.drop_column("factura_lineas", "iva_tipo")
    op.drop_column("facturas", "impuestos_detalle")
    op.drop_column("facturas", "descuento")
    op.drop_column("facturas", "iva_valor")
    op.drop_column("facturas", "impuestos_total")
