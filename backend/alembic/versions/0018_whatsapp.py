"""whatsapp como canal de notificaciones

Revision ID: 0018
Revises: 0017
Create Date: 2026-09-28

Añade `config_notificaciones.whatsapp_numero`: el destino del canal WhatsApp
(Cloud API de Meta), con el número en formato internacional sin `+`.
"""
import sqlalchemy as sa

from alembic import op

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "config_notificaciones",
        sa.Column("whatsapp_numero", sa.String(20), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("config_notificaciones", "whatsapp_numero")
