"""recupera la unicidad de categorias por usuario

Revision ID: 0021
Revises: 0020
Create Date: 2026-09-28

La `0013` creó `uq_categorias_raiz` como índice **parcial**
(`... WHERE padre_id IS NULL`). La `0014` eliminó `categorias.padre_id`, y al
hacerlo PostgreSQL se llevó por delante el índice, porque su cláusula `WHERE`
usaba esa columna. La `0014` solo se acordó de borrar `uq_categorias_hija`.

Resultado: desde la `0014` las **categorías no tenían ninguna garantía de
unicidad en la base**; solo la comprobaba el código de la API. Este test lo
destapó (migrando con datos, no con tablas vacías).

Aquí se recupera el invariante para el modelo actual —las categorías ya son
siempre raíces— y, antes de crear el índice, se **fusionan los duplicados** que
se hayan podido crear mientras la restricción no existía: si no, la migración
fallaría en una base con datos reales.
"""

from alembic import op

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None

# Tablas que apuntan a `categorias` y hay que repuntar al fusionar duplicados
REFERENCIAS = (
    ("transacciones", "categoria_id"),
    ("suscripciones", "categoria_id"),
    ("ingresos_recurrentes", "categoria_id"),
    ("presupuestos", "categoria_id"),
    ("etiquetas", "categoria_id"),
    ("polizas", "categoria_id"),
)


def upgrade() -> None:
    # 1) Fusionar categorías repetidas del mismo usuario (se conserva el id menor)
    cte = """
        WITH ranked AS (
            SELECT id,
                   first_value(id) OVER (PARTITION BY usuario_id, lower(nombre) ORDER BY id) AS conservar,
                   row_number()  OVER (PARTITION BY usuario_id, lower(nombre) ORDER BY id) AS rn
            FROM categorias
        ), dup AS (SELECT id, conservar FROM ranked WHERE rn > 1)
    """
    for tabla, columna in REFERENCIAS:
        op.execute(
            f"{cte} UPDATE {tabla} x SET {columna} = d.conservar "
            f"FROM dup d WHERE x.{columna} = d.id"
        )
    op.execute(f"{cte} DELETE FROM categorias c USING dup d WHERE c.id = d.id")

    # 2) El invariante, ahora sin el `WHERE` que dependía de la columna eliminada
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_categorias_raiz "
        "ON categorias (usuario_id, lower(nombre))"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_categorias_raiz")
