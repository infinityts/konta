"""etiqueta en la suscripción (para que el cargo caiga en el árbol)

Revision ID: 0015
Revises: 0014
Create Date: 2026-09-28
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # La transacción que genere la suscripción hereda esta etiqueta, así el
    # reporte queda como `Suscripciones › Streaming › Netflix`.
    op.add_column("suscripciones", sa.Column("etiqueta_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_suscripciones_etiqueta", "suscripciones", "etiquetas", ["etiqueta_id"], ["id"], ondelete="SET NULL"
    )


def downgrade() -> None:
    op.drop_constraint("fk_suscripciones_etiqueta", "suscripciones", type_="foreignkey")
    op.drop_column("suscripciones", "etiqueta_id")
