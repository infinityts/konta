"""extractos bancarios (Fase 1: ingesta y análisis)

Revision ID: 0025
Revises: 0024
Create Date: 2026-09-28

Dos tablas nuevas: `extractos` (los números que declara el extracto: periodo, corte,
pago, cupo y desglose, más el resultado de la conciliación) y `extracto_movimientos`
(el detalle, con moneda propia, cuotas, monto original en divisa y tasa de cambio).

`tipo` y `formato` son texto, **no** ENUM: son listas que crecerán (más bancos, más
formatos) y quitar un valor de un ENUM no existe en PostgreSQL (ver la nota del 0019).
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "extractos",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "usuario_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column(
            "cuenta_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("cuentas.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column(
            "tarjeta_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tarjetas.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column("tipo", sa.String(10), nullable=False, server_default="tarjeta"),
        sa.Column("formato", sa.String(10), nullable=False, server_default="pdf"),
        sa.Column("banco", sa.String(60), nullable=True),
        sa.Column("nombre_archivo", sa.String(255), nullable=False),
        sa.Column(
            "moneda", sa.String(3), sa.ForeignKey("monedas.codigo"),
            nullable=False, server_default="COP",
        ),
        sa.Column("periodo_desde", sa.Date(), nullable=True),
        sa.Column("periodo_hasta", sa.Date(), nullable=True),
        sa.Column("fecha_corte", sa.Date(), nullable=True),
        sa.Column("fecha_pago", sa.Date(), nullable=True),
        sa.Column("saldo_anterior", sa.Numeric(14, 2), nullable=True),
        sa.Column("compras", sa.Numeric(14, 2), nullable=True),
        sa.Column("intereses", sa.Numeric(14, 2), nullable=True),
        sa.Column("intereses_mora", sa.Numeric(14, 2), nullable=True),
        sa.Column("otros_cargos", sa.Numeric(14, 2), nullable=True),
        sa.Column("abonos", sa.Numeric(14, 2), nullable=True),
        sa.Column("pago_total", sa.Numeric(14, 2), nullable=True),
        sa.Column("pago_minimo", sa.Numeric(14, 2), nullable=True),
        sa.Column("cupo_total", sa.Numeric(14, 2), nullable=True),
        sa.Column("cupo_disponible", sa.Numeric(14, 2), nullable=True),
        sa.Column("conciliacion_ok", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("texto_extraido", sa.Text(), nullable=True),
        sa.Column("conciliacion", sa.Text(), nullable=True),
        sa.Column(
            "creado_en", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_extractos_usuario_id", "extractos", ["usuario_id"])
    op.create_index("ix_extractos_cuenta_id", "extractos", ["cuenta_id"])
    op.create_index("ix_extractos_tarjeta_id", "extractos", ["tarjeta_id"])

    op.create_table(
        "extracto_movimientos",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "extracto_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("extractos.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column(
            "usuario_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("orden", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("fecha", sa.Date(), nullable=True),
        sa.Column("descripcion", sa.String(255), nullable=False, server_default=""),
        sa.Column("valor", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column(
            "moneda", sa.String(3), sa.ForeignKey("monedas.codigo"),
            nullable=False, server_default="COP",
        ),
        sa.Column("saldo", sa.Numeric(14, 2), nullable=True),
        sa.Column("monto_original", sa.Numeric(14, 2), nullable=True),
        sa.Column("moneda_original", sa.String(3), nullable=True),
        sa.Column("tasa_cambio", sa.Numeric(14, 4), nullable=True),
        sa.Column("cuotas_n", sa.Integer(), nullable=True),
        sa.Column("cuotas_total", sa.Integer(), nullable=True),
        sa.Column("cuota_mes", sa.Numeric(14, 2), nullable=True),
        sa.Column("valor_pendiente", sa.Numeric(14, 2), nullable=True),
        sa.Column("titular", sa.String(2), nullable=True),
        sa.Column("tipo", sa.String(20), nullable=False, server_default="otro"),
        sa.Column(
            "categoria_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("categorias.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column(
            "etiqueta_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("etiquetas.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column("origen", sa.String(20), nullable=False, server_default="sin_clasificar"),
        sa.Column(
            "es_informativo", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column(
            "transaccion_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("transacciones.id", ondelete="SET NULL"), nullable=True,
        ),
    )
    op.create_index("ix_extracto_movimientos_extracto_id", "extracto_movimientos", ["extracto_id"])
    op.create_index("ix_extracto_movimientos_usuario_id", "extracto_movimientos", ["usuario_id"])
    op.create_index("ix_extracto_movimientos_fecha", "extracto_movimientos", ["fecha"])


def downgrade() -> None:
    for indice in (
        "ix_extracto_movimientos_fecha",
        "ix_extracto_movimientos_usuario_id",
        "ix_extracto_movimientos_extracto_id",
    ):
        op.drop_index(indice, table_name="extracto_movimientos")
    op.drop_table("extracto_movimientos")

    for indice in ("ix_extractos_tarjeta_id", "ix_extractos_cuenta_id", "ix_extractos_usuario_id"):
        op.drop_index(indice, table_name="extractos")
    op.drop_table("extractos")
