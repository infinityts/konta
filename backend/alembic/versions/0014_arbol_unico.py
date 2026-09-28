"""un solo árbol: Categoría → Etiqueta → Subetiqueta

Revision ID: 0014
Revises: 0013
Create Date: 2026-09-28

Las categorías quedan como **solo raíces**; todo el anidamiento pasa a etiquetas.
Se migran las subcategorías existentes a etiquetas de su categoría raíz y se
borran las etiquetas huérfanas (sin categoría).
"""
from alembic import op
import sqlalchemy as sa

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # a) Crear la etiqueta equivalente por cada subcategoría que no la tenga ya
    op.execute(
        """
        INSERT INTO etiquetas (usuario_id, categoria_id, nombre, creada_en)
        SELECT s.usuario_id, s.padre_id, s.nombre, now()
        FROM categorias s
        WHERE s.padre_id IS NOT NULL
          AND NOT EXISTS (
              SELECT 1 FROM etiquetas e
              WHERE e.usuario_id = s.usuario_id
                AND e.categoria_id = s.padre_id
                AND e.padre_id IS NULL
                AND lower(e.nombre) = lower(s.nombre)
          )
        """
    )

    # b) Los movimientos que apuntaban a la subcategoría pasan a la raíz + su etiqueta
    op.execute(
        """
        UPDATE transacciones t
        SET categoria_id = s.padre_id,
            etiqueta_id  = COALESCE(t.etiqueta_id, e.id)
        FROM categorias s
        JOIN etiquetas e
          ON e.usuario_id = s.usuario_id
         AND e.categoria_id = s.padre_id
         AND e.padre_id IS NULL
         AND lower(e.nombre) = lower(s.nombre)
        WHERE t.categoria_id = s.id
          AND s.padre_id IS NOT NULL
        """
    )

    # c) El resto de referencias también pasan a la raíz
    for tabla in ("suscripciones", "ingresos_recurrentes", "presupuestos", "etiquetas"):
        op.execute(
            f"""
            UPDATE {tabla} x SET categoria_id = s.padre_id
            FROM categorias s
            WHERE x.categoria_id = s.id AND s.padre_id IS NOT NULL
            """
        )

    # d) Fuera las subcategorías
    op.execute("DELETE FROM categorias WHERE padre_id IS NOT NULL")

    # e) Fuera las etiquetas huérfanas (las que quedaron sin categoría)
    op.execute("DELETE FROM etiquetas WHERE categoria_id IS NULL")

    # f) El modelo se cierra: una categoría es siempre raíz
    op.execute("DROP INDEX IF EXISTS uq_categorias_hija")
    op.drop_column("categorias", "padre_id")


def downgrade() -> None:
    op.add_column("categorias", sa.Column("padre_id", sa.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "categorias_padre_id_fkey", "categorias", "categorias", ["padre_id"], ["id"], ondelete="CASCADE"
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_categorias_hija ON categorias (usuario_id, padre_id, lower(nombre)) "
        "WHERE padre_id IS NOT NULL"
    )
