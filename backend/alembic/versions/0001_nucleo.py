"""núcleo: usuarios, monedas, categorías, tarjetas, suscripciones, transacciones

Revision ID: 0001
Revises:
Create Date: 2026-09-27
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

# ENUMs (mismos valores que app/models.py). create_type=False: se crean aquí.
tipo_categoria = postgresql.ENUM("ingreso", "gasto", name="tipo_categoria", create_type=False)
periodicidad = postgresql.ENUM("semanal", "mensual", "trimestral", "anual", name="periodicidad", create_type=False)
estado_suscripcion = postgresql.ENUM("activa", "pausada", "cancelada", name="estado_suscripcion", create_type=False)
tipo_tarjeta = postgresql.ENUM("credito", "debito", name="tipo_tarjeta", create_type=False)
tipo_transaccion = postgresql.ENUM("ingreso", "gasto", name="tipo_transaccion", create_type=False)


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    for enum in (tipo_categoria, periodicidad, estado_suscripcion, tipo_tarjeta, tipo_transaccion):
        enum.create(op.get_bind(), checkfirst=True)

    # --- monedas (catálogo ISO) ---
    op.create_table(
        "monedas",
        sa.Column("codigo", sa.String(3), primary_key=True),
        sa.Column("nombre", sa.String(60), nullable=False),
        sa.Column("simbolo", sa.String(10), nullable=False),
    )
    monedas = sa.table(
        "monedas",
        sa.column("codigo", sa.String(3)),
        sa.column("nombre", sa.String(60)),
        sa.column("simbolo", sa.String(10)),
    )
    op.bulk_insert(
        monedas,
        [
            {"codigo": "COP", "nombre": "Peso colombiano", "simbolo": "$"},
            {"codigo": "USD", "nombre": "Dólar estadounidense", "simbolo": "US$"},
            {"codigo": "EUR", "nombre": "Euro", "simbolo": "€"},
            {"codigo": "MXN", "nombre": "Peso mexicano", "simbolo": "$"},
            {"codigo": "PEN", "nombre": "Sol peruano", "simbolo": "S/"},
            {"codigo": "CLP", "nombre": "Peso chileno", "simbolo": "$"},
            {"codigo": "ARS", "nombre": "Peso argentino", "simbolo": "$"},
            {"codigo": "UYU", "nombre": "Peso uruguayo", "simbolo": "$"},
            {"codigo": "BRL", "nombre": "Real brasileño", "simbolo": "R$"},
            {"codigo": "GBP", "nombre": "Libra esterlina", "simbolo": "£"},
        ],
    )

    # --- usuarios ---
    op.create_table(
        "usuarios",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("nombre", sa.String(120), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("moneda_principal", sa.String(3), sa.ForeignKey("monedas.codigo"), nullable=False, server_default=sa.text("'COP'")),
        sa.Column("creado_en", postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_usuarios_email", "usuarios", ["email"], unique=True)

    # --- categorias ---
    op.create_table(
        "categorias",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("usuario_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False),
        sa.Column("nombre", sa.String(80), nullable=False),
        sa.Column("tipo", tipo_categoria, nullable=False),
        sa.Column("icono", sa.String(40), nullable=True),
        sa.Column("color", sa.String(20), nullable=True),
    )
    op.create_index("ix_categorias_usuario", "categorias", ["usuario_id"])

    # --- tarjetas ---
    op.create_table(
        "tarjetas",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("usuario_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False),
        sa.Column("nombre", sa.String(80), nullable=False),
        sa.Column("banco", sa.String(80), nullable=True),
        sa.Column("tipo", tipo_tarjeta, nullable=False),
        sa.Column("moneda", sa.String(3), sa.ForeignKey("monedas.codigo"), nullable=False, server_default=sa.text("'COP'")),
        sa.Column("dia_corte", sa.Integer(), nullable=True),
        sa.Column("dia_pago", sa.Integer(), nullable=True),
        sa.Column("limite", sa.Numeric(14, 2), nullable=True),
        sa.Column("tasa_interes", sa.Numeric(8, 4), nullable=True),
        sa.Column("activa", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.create_index("ix_tarjetas_usuario", "tarjetas", ["usuario_id"])

    # --- suscripciones ---
    op.create_table(
        "suscripciones",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("usuario_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False),
        sa.Column("nombre", sa.String(120), nullable=False),
        sa.Column("monto", sa.Numeric(14, 2), nullable=False),
        sa.Column("moneda", sa.String(3), sa.ForeignKey("monedas.codigo"), nullable=False, server_default=sa.text("'COP'")),
        sa.Column("periodicidad", periodicidad, nullable=False, server_default=sa.text("'mensual'")),
        sa.Column("fecha_inicio", sa.Date(), nullable=True),
        sa.Column("proximo_pago", sa.Date(), nullable=True),
        sa.Column("categoria_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("categorias.id", ondelete="SET NULL"), nullable=True),
        sa.Column("tarjeta_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tarjetas.id", ondelete="SET NULL"), nullable=True),
        sa.Column("estado", estado_suscripcion, nullable=False, server_default=sa.text("'activa'")),
        sa.Column("notas", sa.Text(), nullable=True),
    )
    op.create_index("ix_suscripciones_usuario", "suscripciones", ["usuario_id"])
    op.create_index("ix_suscripciones_proximo_pago", "suscripciones", ["proximo_pago"])

    # --- transacciones ---
    op.create_table(
        "transacciones",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("usuario_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tipo", tipo_transaccion, nullable=False),
        sa.Column("monto", sa.Numeric(14, 2), nullable=False),
        sa.Column("moneda", sa.String(3), sa.ForeignKey("monedas.codigo"), nullable=False, server_default=sa.text("'COP'")),
        sa.Column("fecha", sa.Date(), nullable=False),
        sa.Column("descripcion", sa.String(255), nullable=True),
        sa.Column("categoria_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("categorias.id", ondelete="SET NULL"), nullable=True),
        sa.Column("tarjeta_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tarjetas.id", ondelete="SET NULL"), nullable=True),
        sa.Column("suscripcion_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("suscripciones.id", ondelete="SET NULL"), nullable=True),
        sa.Column("notas", sa.Text(), nullable=True),
    )
    op.create_index("ix_transacciones_usuario", "transacciones", ["usuario_id"])
    op.create_index("ix_transacciones_fecha", "transacciones", ["fecha"])

    # --- tasas de cambio (multi-moneda) ---
    op.create_table(
        "tasas_cambio",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("moneda_origen", sa.String(3), sa.ForeignKey("monedas.codigo"), nullable=False),
        sa.Column("moneda_destino", sa.String(3), sa.ForeignKey("monedas.codigo"), nullable=False),
        sa.Column("fecha", sa.Date(), nullable=False),
        sa.Column("tasa", sa.Numeric(18, 6), nullable=False),
        sa.Column("fuente", sa.String(120), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("tasas_cambio")
    op.drop_table("transacciones")
    op.drop_table("suscripciones")
    op.drop_table("tarjetas")
    op.drop_table("categorias")
    op.drop_table("usuarios")
    op.drop_table("monedas")
    for enum in (tipo_transaccion, tipo_tarjeta, estado_suscripcion, periodicidad, tipo_categoria):
        enum.drop(op.get_bind(), checkfirst=True)
