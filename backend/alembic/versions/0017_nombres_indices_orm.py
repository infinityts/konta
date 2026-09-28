"""nombres de índice alineados con el ORM

Revision ID: 0017
Revises: 0016
Create Date: 2026-09-28

Las migraciones 0001-0016 crearon los índices con nombres cortos escritos a
mano (`ix_transacciones_usuario`), pero SQLAlchemy nombra los índices de
`index=True` como `ix_<tabla>_<columna>` (`ix_transacciones_usuario_id`).

Eso hacía que `alembic check` (y cualquier `--autogenerate`) reportara ~40
operaciones falsas: "borrar" los índices viejos y "crear" los nuevos, cuando en
realidad son el mismo índice. El riesgo no era cosmético: un autogenerate
aceptado sin leerlo podía tirar índices reales.

Aquí solo se **renombran** (metadato puro, instantáneo, sin reescribir datos) y
de paso queda el índice que faltaba: `metas_ahorro.usuario_id` estaba declarado
`index=True` en el modelo pero ninguna migración lo había creado.
"""
from alembic import op

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None

# (nombre viejo de la migración, nombre que espera el ORM)
RENOMBRES: list[tuple[str, str]] = [
    ("ix_aportes_meta", "ix_aportes_meta_meta_id"),
    ("ix_aportes_usuario", "ix_aportes_meta_usuario_id"),
    ("ix_categorias_usuario", "ix_categorias_usuario_id"),
    ("ix_cuentas_usuario", "ix_cuentas_usuario_id"),
    ("ix_deudas_tarjeta", "ix_deudas_tarjeta_tarjeta_id"),
    ("ix_deudas_usuario", "ix_deudas_tarjeta_usuario_id"),
    ("ix_etiquetas_categoria", "ix_etiquetas_categoria_id"),
    ("ix_etiquetas_usuario", "ix_etiquetas_usuario_id"),
    ("ix_factura_lineas_factura", "ix_factura_lineas_factura_id"),
    ("ix_facturas_usuario", "ix_facturas_usuario_id"),
    ("ix_ingresos_recurrentes_proxima", "ix_ingresos_recurrentes_proxima_ejecucion"),
    ("ix_ingresos_recurrentes_usuario", "ix_ingresos_recurrentes_usuario_id"),
    ("ix_lista_usuario", "ix_lista_mercado_usuario_id"),
    ("ix_metas_usuario", "ix_metas_ahorro_usuario_id"),
    ("ix_precios_producto", "ix_precios_mercado_producto_id"),
    ("ix_precios_usuario", "ix_precios_mercado_usuario_id"),
    ("ix_presupuestos_usuario", "ix_presupuestos_usuario_id"),
    ("ix_productos_usuario", "ix_productos_usuario_id"),
    ("ix_suscripciones_usuario", "ix_suscripciones_usuario_id"),
    ("ix_tarjetas_usuario", "ix_tarjetas_usuario_id"),
    ("ix_transacciones_cuenta", "ix_transacciones_cuenta_id"),
    ("ix_transacciones_usuario", "ix_transacciones_usuario_id"),
]


def upgrade() -> None:
    for viejo, nuevo in RENOMBRES:
        # IF EXISTS: en bases creadas a mano el índice puede faltar; el
        # autogenerate posterior lo reportará si de verdad hace falta.
        op.execute(f'ALTER INDEX IF EXISTS "{viejo}" RENAME TO "{nuevo}"')


def downgrade() -> None:
    for viejo, nuevo in RENOMBRES:
        op.execute(f'ALTER INDEX IF EXISTS "{nuevo}" RENAME TO "{viejo}"')
