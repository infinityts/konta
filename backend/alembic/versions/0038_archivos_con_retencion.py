"""guardar el archivo de la factura con retencion limitada

Revision ID: 0038
Revises: 0037
Create Date: 2026-09-30

Para poder releer una factura con IA (solo cuando el lector normal falla) hace falta el archivo.
Se guarda con retencion limitada por plan: 30 archivos 7 dias en el Basico, 100/30 en Personal,
300/90 en Pro, e ilimitado con uso justo en el plan sin limite.
"""
import sqlalchemy as sa

from alembic import op

revision = "0038"
down_revision = "0037"
branch_labels = None
depends_on = None

PLANES = [
    ("basico", 30, 7, 60),
    ("personal", 100, 30, 200),
    ("pro", 300, 90, 600),
]


def upgrade() -> None:
    for columna, tipo, defecto in (
        ("archivos_incluidos", sa.Integer(), None),
        ("retencion_dias", sa.Integer(), "7"),
        ("almacenamiento_mb", sa.Integer(), "60"),
    ):
        op.add_column(
            "planes",
            sa.Column(columna, tipo, nullable=defecto is None, server_default=defecto),
        )

    for codigo, archivos, dias, mb in PLANES:
        op.execute(
            sa.text(
                "update planes set archivos_incluidos = :a, retencion_dias = :d, "
                "almacenamiento_mb = :m where codigo = :c"
            ).bindparams(a=archivos, d=dias, m=mb, c=codigo)
        )

    op.add_column("facturas", sa.Column("archivo_clave", sa.String(200), nullable=True))
    op.add_column("facturas", sa.Column("archivo_tipo", sa.String(80), nullable=True))
    op.add_column("facturas", sa.Column("archivo_bytes", sa.Integer(), nullable=True))
    op.add_column(
        "facturas", sa.Column("archivo_expira_en", sa.TIMESTAMP(timezone=True), nullable=True)
    )
    op.add_column(
        "facturas",
        sa.Column("leida_con_ia", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.create_index("ix_facturas_archivo_clave", "facturas", ["archivo_clave"])
    op.create_index("ix_facturas_archivo_expira_en", "facturas", ["archivo_expira_en"])


def downgrade() -> None:
    op.drop_index("ix_facturas_archivo_expira_en", table_name="facturas")
    op.drop_index("ix_facturas_archivo_clave", table_name="facturas")
    for columna in ("leida_con_ia", "archivo_expira_en", "archivo_bytes", "archivo_tipo", "archivo_clave"):
        op.drop_column("facturas", columna)
    for columna in ("almacenamiento_mb", "retencion_dias", "archivos_incluidos"):
        op.drop_column("planes", columna)
