"""polizas de seguro (personas y vehiculos) + beneficiarios

Revision ID: 0019
Revises: 0018
Create Date: 2026-09-28

- `polizas`: seguro de vida / salud / vehículo / hogar. Como una suscripción
  tiene prima, periodicidad y `proximo_pago` (el scheduler genera el gasto), más
  la vigencia (inicio/fin) para avisar del vencimiento, los datos del vehículo
  (placa, marca, modelo, valor asegurado) y la cuenta/tarjeta del cargo.
- `beneficiarios`: nombre, parentesco y porcentaje (seguros de vida).
- `transacciones.poliza_id`: trazabilidad del gasto generado por una póliza.
- `periodicidad` gana el valor `semestral`, que las pólizas usan.

Nota de downgrade: PostgreSQL no permite **quitar** un valor de un ENUM, así que
`semestral` se queda en el tipo (inofensivo: nadie lo usa sin las tablas).
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1) Vocabulario: las pólizas se pagan semestralmente a menudo
    op.execute("ALTER TYPE periodicidad ADD VALUE IF NOT EXISTS 'semestral'")

    # 2) Pólizas
    op.create_table(
        "polizas",
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
        sa.Column("tipo", sa.String(20), nullable=False, server_default=sa.text("'vida'")),
        sa.Column("aseguradora", sa.String(120), nullable=False),
        sa.Column("numero_poliza", sa.String(60), nullable=True),
        sa.Column("asegurado_nombre", sa.String(120), nullable=True),
        sa.Column("placa", sa.String(10), nullable=True),
        sa.Column("marca", sa.String(60), nullable=True),
        sa.Column("modelo", sa.String(60), nullable=True),
        sa.Column("anio", sa.Integer(), nullable=True),
        sa.Column("valor_asegurado", sa.Numeric(14, 2), nullable=True),
        sa.Column("prima", sa.Numeric(14, 2), nullable=False),
        sa.Column(
            "moneda",
            sa.String(3),
            sa.ForeignKey("monedas.codigo"),
            nullable=False,
            server_default=sa.text("'COP'"),
        ),
        sa.Column(
            "periodicidad",
            postgresql.ENUM(name="periodicidad", create_type=False),
            nullable=False,
            server_default=sa.text("'mensual'"),
        ),
        sa.Column("fecha_inicio", sa.Date(), nullable=True),
        sa.Column("fecha_fin", sa.Date(), nullable=True),
        sa.Column("proximo_pago", sa.Date(), nullable=True),
        sa.Column(
            "renovacion_automatica", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column(
            "categoria_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("categorias.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "etiqueta_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("etiquetas.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "tarjeta_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tarjetas.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "cuenta_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("cuentas.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "estado",
            postgresql.ENUM(name="estado_suscripcion", create_type=False),
            nullable=False,
            server_default=sa.text("'activa'"),
        ),
        sa.Column("notas", sa.Text(), nullable=True),
        sa.Column(
            "creada_en",
            postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_polizas_usuario_id", "polizas", ["usuario_id"])
    op.create_index("ix_polizas_proximo_pago", "polizas", ["proximo_pago"])

    # 3) Beneficiarios
    op.create_table(
        "beneficiarios",
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
        sa.Column("porcentaje", sa.Numeric(5, 2), nullable=True),
        sa.Column(
            "creada_en",
            postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_beneficiarios_usuario_id", "beneficiarios", ["usuario_id"])
    op.create_index("ix_beneficiarios_poliza_id", "beneficiarios", ["poliza_id"])

    # 4) El gasto generado apunta a su póliza
    op.add_column(
        "transacciones",
        sa.Column("poliza_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_transacciones_poliza",
        "transacciones",
        "polizas",
        ["poliza_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_transacciones_poliza_id", "transacciones", ["poliza_id"])


def downgrade() -> None:
    op.drop_index("ix_transacciones_poliza_id", table_name="transacciones")
    op.drop_constraint("fk_transacciones_poliza", "transacciones", type_="foreignkey")
    op.drop_column("transacciones", "poliza_id")

    op.drop_index("ix_beneficiarios_poliza_id", table_name="beneficiarios")
    op.drop_index("ix_beneficiarios_usuario_id", table_name="beneficiarios")
    op.drop_table("beneficiarios")

    op.drop_index("ix_polizas_proximo_pago", table_name="polizas")
    op.drop_index("ix_polizas_usuario_id", table_name="polizas")
    op.drop_table("polizas")
    # `semestral` se queda en el ENUM, y es **deliberado**:
    #
    # 1. No hay forma de quitarlo: `ALTER TYPE ... DROP VALUE` no existe (da error
    #    de sintaxis; la única vía es recrear el tipo).
    # 2. Aunque se pudiera, no se debe: `semestral` es una función viva (una póliza
    #    o una suscripción que se paga cada 6 meses), con su matemática en
    #    `recurrencia.factor_mensual` (1/6), sus opciones en la UI y sus tests.
    #    Quitarlo sería borrar la función, no limpiar un resto.
    #
    # Si algún día hay que quitarlo de verdad, esta es la receta **verificada**:
    #   1. `ALTER TABLE {suscripciones,polizas} ALTER COLUMN periodicidad DROP DEFAULT`
    #      (sin esto: `DatatypeMismatch: default for column ... cannot be cast`);
    #   2. migrar antes las filas con el valor (si no:
    #      `InvalidTextRepresentation: invalid input value for enum ...`), y ojo:
    #      decidir a qué pasan es una decisión **de datos**, no técnica (una póliza
    #      semestral hecha mensual duplica su peso en el flujo de caja);
    #   3. `CREATE TYPE periodicidad_nueva AS ENUM (los que queden)`;
    #   4. `ALTER TABLE ... ALTER COLUMN periodicidad TYPE periodicidad_nueva
    #      USING periodicidad::text::periodicidad_nueva` en las dos tablas;
    #   5. `DROP TYPE periodicidad; ALTER TYPE periodicidad_nueva RENAME TO periodicidad`;
    #   6. restaurar el `DEFAULT` y quitar `Periodicidad.SEMESTRAL` del código.
    #
    # Y recuerda: `alembic check` **no** compara las etiquetas del ENUM. De eso se
    # encarga `test_los_enums_de_la_base_coinciden_con_los_del_codigo`.
