"""config_notificaciones (Telegram / email)

Revision ID: 0008
Revises: 0007
Create Date: 2026-09-27
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "config_notificaciones",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("usuario_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("canal", sa.String(20), nullable=False, server_default=sa.text("'telegram'")),
        sa.Column("telegram_chat_id", sa.String(64), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("dias_anticipacion", sa.Integer(), nullable=False, server_default=sa.text("5")),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("ultima_notificacion", sa.Date(), nullable=True),
        sa.Column("creada_en", postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    )


def downgrade() -> None:
    op.drop_table("config_notificaciones")
