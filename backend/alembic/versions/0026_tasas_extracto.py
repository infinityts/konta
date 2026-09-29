"""tasa de interes del extracto (Fase 4: valor acumulado)

Revision ID: 0026
Revises: 0025
Create Date: 2026-09-28

Guarda la **tasa real** que cobra el banco, que hasta ahora se leía y se tiraba:

- `extracto_movimientos.tasa_ea`: la tasa de cada compra (el extracto de Davivienda la trae
  por fila: `1,9648% 26,30%` = 1,9648 % M.V y 26,30 % E.A.).
- `extractos.tasa_ea` y `extractos.tasa_mv`: la que declare el corte en su resumen.

Se guardan como **fracción** (0,2630), igual que `tarjetas.tasa_interes_ea`, para que el
simulador pueda usarlas sin conversiones raras.
"""
import sqlalchemy as sa

from alembic import op

revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("extractos", sa.Column("tasa_mv", sa.Numeric(8, 4), nullable=True))
    op.add_column("extractos", sa.Column("tasa_ea", sa.Numeric(8, 4), nullable=True))
    op.add_column(
        "extracto_movimientos", sa.Column("tasa_ea", sa.Numeric(8, 4), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("extracto_movimientos", "tasa_ea")
    op.drop_column("extractos", "tasa_ea")
    op.drop_column("extractos", "tasa_mv")
