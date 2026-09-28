"""personas aseguradas por poliza (poliza_asegurados)

Revision ID: 0020
Revises: 0019
Create Date: 2026-09-28

Una póliza familiar cubre a varias personas. `polizas.asegurado_nombre` sigue
siendo la persona asegurada principal (o el tomador, en vehículo) y sirve para el
título; esta tabla es el detalle de quiénes están cubiertos, con parentesco,
fecha de nacimiento y cuál es el titular.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "poliza_asegurados",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "usuario_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("usuarios.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "poliza_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("polizas.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("nombre", sa.String(120), nullable=False),
        sa.Column("parentesco", sa.String(60), nullable=True),
        sa.Column("fecha_nacimiento", sa.Date(), nullable=True),
        sa.Column("es_titular", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "creada_en",
            postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_poliza_asegurados_usuario_id", "poliza_asegurados", ["usuario_id"])
    op.create_index("ix_poliza_asegurados_poliza_id", "poliza_asegurados", ["poliza_id"])


def downgrade() -> None:
    op.drop_index("ix_poliza_asegurados_poliza_id", table_name="poliza_asegurados")
    op.drop_index("ix_poliza_asegurados_usuario_id", table_name="poliza_asegurados")
    op.drop_table("poliza_asegurados")
