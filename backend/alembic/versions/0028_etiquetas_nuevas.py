"""etiquetas nuevas de mercado (bebidas, panadería, snacks, congelados) y mascotas

Revision ID: 0028
Revises: 0027
Create Date: 2026-09-29

El diccionario ganó palabras para **Bebidas**, **Panadería**, **Snacks** y **Congelados**
(que antes caían todas revueltas en Despensa) y para las etiquetas de **Mascotas**, que
existían en la cuenta pero sin ninguna palabra: un concentrado no se podía clasificar.

Como el clasificador empareja contra **nombres de etiquetas**, sin crearlas esas palabras
no clasifican nada. Misma mecánica que la 0027: aditiva, solo lo que falta, y solo donde
la categoría existe con ese nombre.
"""
import sqlalchemy as sa

from alembic import op

revision = "0028"
down_revision = "0027"
branch_labels = None
depends_on = None

ETIQUETAS: tuple[tuple[str, str], ...] = (
    ("Mercado", "Bebidas"),
    ("Mercado", "Panadería"),
    ("Mercado", "Snacks"),
    ("Mercado", "Congelados"),
    ("Mascotas", "Alimento"),
    ("Mascotas", "Veterinario"),
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
