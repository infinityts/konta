"""renglones que el usuario borra siempre: no son articulos

Revision ID: 0034
Revises: 0033
Create Date: 2026-09-30

Un recibo trae «Nit: 900123456», «Cajero: 12» o «Cambio: 0» entre los renglones y el lector los
puede tomar por productos. Cuando el usuario los borra se guarda el patron; a la segunda vez se
descartan solos.
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0034"
down_revision = "0033"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "patrones_ignorados",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "usuario_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("usuarios.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("patron", sa.String(80), nullable=False),
        sa.Column("ejemplo", sa.String(120), nullable=False),
        sa.Column("veces", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "creada_en", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
        sa.Column(
            "actualizada_en",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("usuario_id", "patron", name="uq_patrones_ignorados_patron"),
    )


def downgrade() -> None:
    op.drop_table("patrones_ignorados")
