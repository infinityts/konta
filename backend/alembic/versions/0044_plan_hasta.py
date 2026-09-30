"""hasta cuándo vale el plan de pago

Revision ID: 0044
Revises: 0043
Create Date: 2026-09-30

Sin esto, un solo pago dejaba el plan para siempre: no había vencimiento y el negocio era de
ingreso único con coste mensual. Con `plan_hasta`, un plan de pago vale 30 días y al vencer se
vuelve al plan base (las lecturas compradas aparte se respetan: esas se pagaron).
"""
import sqlalchemy as sa

from alembic import op

revision = "0044"
down_revision = "0043"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("usuarios", sa.Column("plan_hasta", sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column("usuarios", "plan_hasta")
