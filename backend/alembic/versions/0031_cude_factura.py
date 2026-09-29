"""CUDE y enlace de la DIAN leídos del QR de la factura

Revision ID: 0031
Revises: 0030
Create Date: 2026-09-29

La factura electrónica trae un QR con la URL de consulta de la DIAN y el **CUDE** (código
único del documento). Guardarlo sirve para no depender del OCR —el código viene del QR, no
de adivinar caracteres— y para **detectar duplicados**: la misma factura subida dos veces
tiene el mismo CUDE.
"""
import sqlalchemy as sa

from alembic import op

revision = "0031"
down_revision = "0030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("facturas", sa.Column("cude", sa.String(length=96), nullable=True))
    op.add_column("facturas", sa.Column("url_dian", sa.String(length=500), nullable=True))
    op.create_index("ix_facturas_cude", "facturas", ["cude"])


def downgrade() -> None:
    op.drop_index("ix_facturas_cude", table_name="facturas")
    op.drop_column("facturas", "url_dian")
    op.drop_column("facturas", "cude")
