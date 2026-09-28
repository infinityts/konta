"""etiquetas dentro de categorías + nombres únicos entre hermanos

Revision ID: 0013
Revises: 0012
Create Date: 2026-09-28

Modelo: Categoría → Etiqueta → Subetiqueta.

Regla de unicidad: dos hermanos (mismo padre) no pueden llamarse igual, sin
distinguir mayúsculas. En categorías distintas el nombre sí se puede repetir.
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def _limpiar_duplicados(
    tabla: str, particion: str, referencias: list[tuple[str, str]], orden: str = "creada_en, id"
) -> None:
    """Conserva un hermano, repunta las referencias y borra el resto.

    `orden` define cuál se conserva. `categorias` no tiene `creada_en`, así que
    ahí se ordena por `id`.
    """
    cte = f"""
        WITH ranked AS (
            SELECT id,
                   first_value(id) OVER (PARTITION BY {particion} ORDER BY {orden}) AS conservar,
                   row_number()  OVER (PARTITION BY {particion} ORDER BY {orden}) AS rn
            FROM {tabla}
        ), dup AS (SELECT id, conservar FROM ranked WHERE rn > 1)
    """
    for tabla_ref, columna in referencias:
        op.execute(f"{cte} UPDATE {tabla_ref} x SET {columna} = d.conservar FROM dup d WHERE x.{columna} = d.id")
    op.execute(f"{cte} DELETE FROM {tabla} e USING dup d WHERE e.id = d.id")


def upgrade() -> None:
    # 1) La etiqueta vive dentro de una categoría
    op.add_column("etiquetas", sa.Column("categoria_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_etiquetas_categoria", "etiquetas", "categorias", ["categoria_id"], ["id"], ondelete="CASCADE"
    )
    op.create_index("ix_etiquetas_categoria", "etiquetas", ["categoria_id"])

    # 2) Limpiar duplicados existentes (el usuario eligió borrarlos)
    _limpiar_duplicados(
        "etiquetas",
        "usuario_id, padre_id, lower(nombre)",
        [("transacciones", "etiqueta_id"), ("etiquetas", "padre_id")],
    )
    _limpiar_duplicados(
        "categorias",
        "usuario_id, padre_id, lower(nombre)",
        [
            ("transacciones", "categoria_id"),
            ("suscripciones", "categoria_id"),
            ("ingresos_recurrentes", "categoria_id"),
            ("presupuestos", "categoria_id"),
            ("etiquetas", "categoria_id"),
            ("categorias", "padre_id"),
        ],
        orden="id",  # categorias no tiene creada_en
    )

    # 3) Unicidad entre hermanos (sin distinguir mayúsculas)
    op.execute(
        "CREATE UNIQUE INDEX uq_categorias_raiz ON categorias (usuario_id, lower(nombre)) "
        "WHERE padre_id IS NULL"
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_categorias_hija ON categorias (usuario_id, padre_id, lower(nombre)) "
        "WHERE padre_id IS NOT NULL"
    )
    # COALESCE para que las etiquetas sin categoría tampoco se repitan
    op.execute(
        "CREATE UNIQUE INDEX uq_etiquetas_raiz ON etiquetas "
        "(usuario_id, COALESCE(categoria_id, '00000000-0000-0000-0000-000000000000'::uuid), lower(nombre)) "
        "WHERE padre_id IS NULL"
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_etiquetas_hija ON etiquetas (usuario_id, padre_id, lower(nombre)) "
        "WHERE padre_id IS NOT NULL"
    )


def downgrade() -> None:
    for idx in ("uq_etiquetas_hija", "uq_etiquetas_raiz", "uq_categorias_hija", "uq_categorias_raiz"):
        op.execute(f"DROP INDEX IF EXISTS {idx}")
    op.drop_index("ix_etiquetas_categoria", table_name="etiquetas")
    op.drop_constraint("fk_etiquetas_categoria", "etiquetas", type_="foreignkey")
    op.drop_column("etiquetas", "categoria_id")
