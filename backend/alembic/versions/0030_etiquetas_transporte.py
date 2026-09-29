"""etiquetas Parqueadero y Peajes en Transporte

Revision ID: 0030
Revises: 0029
Create Date: 2026-09-29

Un recibo de parqueadero no es una compra de artículos: es un servicio con un solo
total. Para poder clasificarlo hacían falta las etiquetas **Parqueadero** y **Peajes**
dentro de Transporte (que solo tenía Gasolina).

Misma mecánica que las migraciones 0027 y 0028: aditiva, solo lo que falta y solo donde
la categoría existe con ese nombre.
"""
import sqlalchemy as sa

from alembic import op

revision = "0030"
down_revision = "0029"
branch_labels = None
depends_on = None

ETIQUETAS: tuple[tuple[str, str], ...] = (
    ("Transporte", "Parqueadero"),
    ("Transporte", "Peajes"),
)

_INSERTAR = sa.text(
    """
    INSERT INTO etiquetas (usuario_id, nombre, categoria_id)
    SELECT u.id, :nombre_nuevo, c.id
    FROM usuarios u
    JOIN categorias c
      ON c.usuario_id = u.id
     AND lower(c.nombre) = lower(:categoria)
    WHERE NOT EXISTS (
        SELECT 1 FROM etiquetas e
        WHERE e.usuario_id = u.id
          AND e.padre_id IS NULL
          AND lower(e.nombre) = lower(:nombre_busca)
    )
    """
)


def upgrade() -> None:
    conexion = op.get_bind()
    for categoria, nombre in ETIQUETAS:
        conexion.execute(
            _INSERTAR,
            {"categoria": categoria, "nombre_nuevo": nombre, "nombre_busca": nombre},
        )


def downgrade() -> None:
    """Sin vuelta: borrar etiquetas se llevaría movimientos ya clasificados con ellas."""
