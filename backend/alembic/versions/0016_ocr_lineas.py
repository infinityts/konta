"""OCR por línea: factura_lineas y reglas_ocr

Revision ID: 0016
Revises: 0015
Create Date: 2026-09-28

- `factura_lineas`: cada artículo detectado en el recibo, con su etiqueta sugerida.
  Una factura pasa de 1 a N transacciones.
- `reglas_ocr`: lo que el usuario corrige, para clasificar solo la próxima vez.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "factura_lineas",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("factura_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("facturas.id", ondelete="CASCADE"), nullable=False),
        sa.Column("descripcion", sa.String(200), nullable=False),
        sa.Column("cantidad", sa.Numeric(12, 3), nullable=True),
        sa.Column("valor_unitario", sa.Numeric(14, 2), nullable=True),
        sa.Column("valor_total", sa.Numeric(14, 2), nullable=False),
        sa.Column("etiqueta_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("etiquetas.id", ondelete="SET NULL"), nullable=True),
        sa.Column("origen", sa.String(20), nullable=False, server_default="sin_clasificar"),
        sa.Column("confianza", sa.Numeric(4, 3), nullable=True),
        sa.Column("orden", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("transaccion_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("transacciones.id", ondelete="SET NULL"), nullable=True),
        sa.Column("creada_en", postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_factura_lineas_factura", "factura_lineas", ["factura_id"])

    op.create_table(
        "reglas_ocr",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("usuario_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False),
        sa.Column("patron", sa.String(120), nullable=False),
        sa.Column("etiqueta_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("etiquetas.id", ondelete="CASCADE"), nullable=False),
        sa.Column("veces_usada", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("creada_en", postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("actualizada_en", postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("usuario_id", "patron", name="uq_reglas_ocr_patron"),
    )


def downgrade() -> None:
    op.drop_table("reglas_ocr")
    op.drop_table("factura_lineas")
