"""plan de PDFs ilimitados con tope de peso

Revision ID: 0043
Revises: 0042
Create Date: 2026-09-30

Lo que cuesta de verdad es el espacio, no el número de archivos. Este plan quita el límite de
cantidad (archivos_incluidos = NULL) y pone el tope donde sí importa: el peso, con más días de
retención que el Básico.

El tope de 1 GB sale de lo medido: los documentos del usuario pesan 0,16 MB de media (mediana
0,10), así que 1 GB son del orden de 6.000 documentos: un tope que no molesta al uso normal y sí
acota el abuso. El precio es **provisional**: se ajusta con el informe de promedios del mes.
"""
import sqlalchemy as sa

from alembic import op

revision = "0043"
down_revision = "0042"
branch_labels = None
depends_on = None

PLAN = {
    "codigo": "ilimitado",
    "nombre": "Ilimitado",
    "precio_mes": 19900,
    "lecturas_ia": 300,
    "consultas_asistente": 200,
    "archivos_incluidos": None,  # NULL = sin límite de cantidad
    "retencion_dias": 15,
    "almacenamiento_mb": 1024,
    "activo": True,
    "orden": 4,
}


def upgrade() -> None:
    planes = sa.table(
        "planes",
        sa.column("codigo", sa.String),
        sa.column("nombre", sa.String),
        sa.column("precio_mes", sa.Numeric),
        sa.column("lecturas_ia", sa.Integer),
        sa.column("consultas_asistente", sa.Integer),
        sa.column("archivos_incluidos", sa.Integer),
        sa.column("retencion_dias", sa.Integer),
        sa.column("almacenamiento_mb", sa.Integer),
        sa.column("activo", sa.Boolean),
        sa.column("orden", sa.Integer),
    )
    op.bulk_insert(planes, [PLAN])


def downgrade() -> None:
    op.execute(sa.text("delete from planes where codigo = 'ilimitado'"))
