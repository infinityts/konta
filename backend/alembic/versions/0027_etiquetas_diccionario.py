"""completa las etiquetas del diccionario en las cuentas que ya existen

Revision ID: 0027
Revises: 0026
Create Date: 2026-09-29

El clasificador del OCR **empareja palabras clave contra nombres de etiquetas**, así que
una cuenta creada antes de que existiera alguna de esas etiquetas (o a la que le borraron
una) se queda sin poder clasificar: en una cuenta real, sin `Lácteos y huevos` no había
forma de etiquetar leche, quesos ni yogures, y sin `Cuidado personal` no se etiquetaban
los cepillos ni los desodorantes.

La app ya siembra estas etiquetas al registrar (`defaults.sembrar_etiquetas_diccionario`) y
tiene un botón para hacerlo a mano, pero eso deja fuera a las cuentas anteriores. Esta
migración se las completa a todas.

Es **aditiva y conservadora**: solo inserta lo que falta, solo donde la categoría existe
con ese nombre (si la renombraron, no toca nada) y no toca ninguna etiqueta existente.
"""
import sqlalchemy as sa

from alembic import op

revision = "0027"
down_revision = "0026"
branch_labels = None
depends_on = None

# Las mismas que `defaults.ETIQUETAS_DICCIONARIO`. Van escritas aquí a propósito: una
# migración no debe depender de código que puede cambiar después.
ETIQUETAS: tuple[tuple[str, str], ...] = (
    ("Mercado", "Carnes"),
    ("Mercado", "Frutas y verduras"),
    ("Mercado", "Lácteos y huevos"),
    ("Mercado", "Despensa"),
    ("Mercado", "Aseo del hogar"),
    ("Mercado", "Cuidado personal"),
    ("Transporte", "Gasolina"),
    ("Otros gastos", "Ropa"),
    ("Otros gastos", "Calzado"),
    ("Otros gastos", "Tecnología"),
)

# Dos parámetros para el mismo texto a propósito: PostgreSQL no deja deducir un solo tipo
# cuando el mismo parámetro se usa como valor de una columna `varchar` y a la vez dentro
# de un `lower(...)`. Separarlos evita «inconsistent types deduced for parameter».
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
    """No se revierte: borrar etiquetas podría llevarse por delante movimientos que el
    usuario ya clasificó con ellas. Es una migración de datos aditiva y sin vuelta."""
