"""el cupo utilizado que declara el corte

Revision ID: 0032
Revises: 0031
Create Date: 2026-09-29

El CMR declara «Has utilizado: $2.771.831,16». Hasta ahora solo se calculaba
`cupo_total - cupo_disponible`, así que el control del cupo no comprobaba nada. Se guarda el
valor declarado para poder compararlo (y enseñarlo sin recalcularlo).
"""
import sqlalchemy as sa

from alembic import op

revision = "0032"
down_revision = "0031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("extractos", sa.Column("cupo_utilizado", sa.Numeric(14, 2), nullable=True))


def downgrade() -> None:
    op.drop_column("extractos", "cupo_utilizado")
