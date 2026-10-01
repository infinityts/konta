"""Modelos del núcleo de Finly (multi-usuario, multi-moneda).

El esquema real lo crea Alembic (alembic/versions/0001_nucleo.py). Estos modelos
son el espejo ORM. Convenciones: UUID vía aplicación, montos con Numeric(14,2),
monedas como código ISO (CHAR(3)) referenciando `monedas`.
"""

from __future__ import annotations

import enum
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


def _ahora() -> datetime:
    return datetime.now(UTC)


# --- Vocabulario congelado (coincide con la migración 0001) ---


class TipoCategoria(enum.StrEnum):
    INGRESO = "ingreso"
    GASTO = "gasto"


class Periodicidad(enum.StrEnum):
    SEMANAL = "semanal"
    MENSUAL = "mensual"
    TRIMESTRAL = "trimestral"
    SEMESTRAL = "semestral"
    ANUAL = "anual"


class EstadoSuscripcion(enum.StrEnum):
    ACTIVA = "activa"
    PAUSADA = "pausada"
    CANCELADA = "cancelada"


class TipoTarjeta(enum.StrEnum):
    CREDITO = "credito"
    DEBITO = "debito"


class TipoTransaccion(enum.StrEnum):
    INGRESO = "ingreso"
    GASTO = "gasto"
    # Mover dinero entre dos cuentas propias: **no** es ingreso ni gasto, así que
    # queda fuera de los reportes, del flujo de caja y de los presupuestos.
    TRANSFERENCIA = "transferencia"


def _enum(cls: type[enum.Enum], name: str) -> PG_ENUM:
    return PG_ENUM(
        cls,
        name=name,
        create_type=False,
        values_callable=lambda e: [m.value for m in e],
    )


_tipo_categoria = _enum(TipoCategoria, "tipo_categoria")
_periodicidad = _enum(Periodicidad, "periodicidad")
_estado_suscripcion = _enum(EstadoSuscripcion, "estado_suscripcion")
_tipo_tarjeta = _enum(TipoTarjeta, "tipo_tarjeta")
_tipo_transaccion = _enum(TipoTransaccion, "tipo_transaccion")


# --- Entidades ---


class Moneda(Base):
    __tablename__ = "monedas"

    codigo: Mapped[str] = mapped_column(String(3), primary_key=True)
    nombre: Mapped[str] = mapped_column(String(60), nullable=False)
    simbolo: Mapped[str] = mapped_column(String(10), nullable=False)


class IntentosLogin(Base):
    """Los fallos de contraseña, por correo y por IP.

    Vive en la base y no en memoria: si se reinicia el backend, el bloqueo tiene que seguir en pie
    (si no, bastaría con esperar a un despliegue para volver a probar).
    """

    __tablename__ = "intentos_login"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    # "email:alguien@ejemplo.com" o "ip:1.2.3.4"
    clave: Mapped[str] = mapped_column(String(180), nullable=False, unique=True, index=True)
    intentos: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Hasta cuándo está bloqueada esa clave (UTC). None = no está bloqueada.
    bloqueado_hasta: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )


class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    nombre: Mapped[str] = mapped_column(String(120), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    # Su plan (catálogo en `planes`) y las lecturas que haya comprado aparte
    plan_codigo: Mapped[str] = mapped_column(
        String(24), nullable=False, default="basico", server_default="basico"
    )
    lecturas_extra: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    # Hasta cuándo vale el plan de pago. NULL = plan base (sin vencimiento). Un pago lo pone a 30
    # días; si se renueva antes, se extiende desde donde estaba.
    plan_hasta: Mapped[date | None] = mapped_column(Date, nullable=True)
    moneda_principal: Mapped[str] = mapped_column(
        ForeignKey("monedas.codigo"), nullable=False, default="COP"
    )
    creado_en: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=_ahora)


class TasaCambio(Base):
    __tablename__ = "tasas_cambio"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    moneda_origen: Mapped[str] = mapped_column(ForeignKey("monedas.codigo"), nullable=False)
    moneda_destino: Mapped[str] = mapped_column(ForeignKey("monedas.codigo"), nullable=False)
    fecha: Mapped[date] = mapped_column(Date, nullable=False)
    tasa: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    fuente: Mapped[str | None] = mapped_column(String(120), nullable=True)


class Categoria(Base):
    __tablename__ = "categorias"

    # Unicidad del nombre por usuario, sin distinguir mayúsculas. La categoría es
    # siempre raíz (el anidamiento vive en etiquetas), así que no lleva `WHERE`.
    # Se declara aquí para que coincida con el índice de la migración 0021: la
    # 0014 se llevó el índice parcial que creó la 0013 al borrar `padre_id`.
    __table_args__ = (
        Index("uq_categorias_raiz", "usuario_id", text("lower(nombre)"), unique=True),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    usuario_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True
    )
    nombre: Mapped[str] = mapped_column(String(80), nullable=False)
    tipo: Mapped[TipoCategoria] = mapped_column(_tipo_categoria, nullable=False)
    icono: Mapped[str | None] = mapped_column(String(40), nullable=True)
    color: Mapped[str | None] = mapped_column(String(20), nullable=True)


class Tarjeta(Base):
    __tablename__ = "tarjetas"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    usuario_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True
    )
    nombre: Mapped[str] = mapped_column(String(80), nullable=False)
    banco: Mapped[str | None] = mapped_column(String(80), nullable=True)
    tipo: Mapped[TipoTarjeta] = mapped_column(_tipo_tarjeta, nullable=False)
    moneda: Mapped[str] = mapped_column(ForeignKey("monedas.codigo"), nullable=False, default="COP")
    dia_corte: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dia_pago: Mapped[int | None] = mapped_column(Integer, nullable=True)
    limite: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    tasa_interes: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    tasa_interes_ea: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    # Solo para tarjetas DÉBITO: la cuenta de la que descuentan (la tarjeta es un
    # instrumento de esa cuenta, no un saldo aparte). En crédito va NULL.
    cuenta_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("cuentas.id", ondelete="SET NULL"), nullable=True
    )
    activa: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Suscripcion(Base):
    __tablename__ = "suscripciones"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    usuario_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True
    )
    nombre: Mapped[str] = mapped_column(String(120), nullable=False)
    monto: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    moneda: Mapped[str] = mapped_column(ForeignKey("monedas.codigo"), nullable=False, default="COP")
    periodicidad: Mapped[Periodicidad] = mapped_column(_periodicidad, nullable=False, default=Periodicidad.MENSUAL)
    fecha_inicio: Mapped[date | None] = mapped_column(Date, nullable=True)
    proximo_pago: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    categoria_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("categorias.id", ondelete="SET NULL"), nullable=True
    )
    tarjeta_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("tarjetas.id", ondelete="SET NULL"), nullable=True
    )
    # Etiqueta (dentro de la categoría) para que el cargo caiga en el árbol correcto
    etiqueta_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("etiquetas.id", ondelete="SET NULL"), nullable=True
    )
    # De dónde sale el dinero: sin esto, cada gasto que generaba el job quedaba
    # como «movimiento sin cuenta» y no movía ningún saldo.
    cuenta_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("cuentas.id", ondelete="SET NULL"), nullable=True, index=True
    )
    estado: Mapped[EstadoSuscripcion] = mapped_column(_estado_suscripcion, nullable=False, default=EstadoSuscripcion.ACTIVA)
    notas: Mapped[str | None] = mapped_column(Text, nullable=True)


class Transaccion(Base):
    __tablename__ = "transacciones"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    usuario_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tipo: Mapped[TipoTransaccion] = mapped_column(_tipo_transaccion, nullable=False)
    monto: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    moneda: Mapped[str] = mapped_column(ForeignKey("monedas.codigo"), nullable=False, default="COP")
    fecha: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    descripcion: Mapped[str | None] = mapped_column(String(255), nullable=True)
    categoria_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("categorias.id", ondelete="SET NULL"), nullable=True
    )
    tarjeta_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("tarjetas.id", ondelete="SET NULL"), nullable=True
    )
    suscripcion_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("suscripciones.id", ondelete="SET NULL"), nullable=True
    )
    # Lo rellena el servidor cuando el ingreso lo genera un ingreso recurrente
    ingreso_recurrente_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("ingresos_recurrentes.id", ondelete="SET NULL"), nullable=True
    )
    etiqueta_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("etiquetas.id", ondelete="SET NULL"), nullable=True
    )
    cuenta_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("cuentas.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # Solo en una transferencia: la cuenta que **recibe** (la de origen va en
    # `cuenta_id`). En gastos e ingresos es NULL.
    cuenta_destino_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("cuentas.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # Gasto generado por una póliza (como `suscripcion_id` para las suscripciones)
    poliza_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("polizas.id", ondelete="SET NULL"), nullable=True, index=True
    )
    notas: Mapped[str | None] = mapped_column(Text, nullable=True)


class PeriodicidadIngreso(enum.StrEnum):
    DIARIO = "diario"
    SEMANAL = "semanal"
    MENSUAL = "mensual"


_periodicidad_ingreso = _enum(PeriodicidadIngreso, "periodicidad_ingreso")


class IngresoRecurrente(Base):
    """Ingreso recurrente (diario/semanal/mensual): al llegar `proxima_ejecucion`,
    el scheduler genera una transacción de tipo ingreso automáticamente."""

    __tablename__ = "ingresos_recurrentes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    usuario_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True
    )
    nombre: Mapped[str] = mapped_column(String(120), nullable=False)
    monto: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    moneda: Mapped[str] = mapped_column(ForeignKey("monedas.codigo"), nullable=False, default="COP")
    periodicidad: Mapped[PeriodicidadIngreso] = mapped_column(_periodicidad_ingreso, nullable=False)
    # mensual: día del mes (1-31); semanal: día de la semana (0=Lunes … 6=Domingo); diario: None
    dia: Mapped[int | None] = mapped_column(Integer, nullable=True)
    proxima_ejecucion: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    categoria_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("categorias.id", ondelete="SET NULL"), nullable=True
    )
    # En qué cuenta entra (mismo motivo que en las suscripciones)
    cuenta_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("cuentas.id", ondelete="SET NULL"), nullable=True, index=True
    )
    activa: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    creada_en: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=_ahora)


class Etiqueta(Base):
    """Etiquetas y subetiquetas, siempre **dentro de una categoría**.

    Jerarquía: `Categoría → Etiqueta → Subetiqueta`.

    - `categoria_id`: la categoría a la que pertenece.
    - `padre_id`: NULL = etiqueta; con valor = subetiqueta de esa etiqueta.

    Los nombres son únicos **entre hermanos** (mismo padre), sin distinguir
    mayúsculas. En categorías distintas sí se puede repetir el nombre.
    """

    __tablename__ = "etiquetas"

    # Unicidad entre hermanos (sin distinguir mayúsculas). Se declaran aquí para
    # que el ORM refleje EXACTAMENTE los índices funcionales que crea la
    # migración 0013; sin esto, `alembic check` propone borrarlos.
    __table_args__ = (
        Index(
            "uq_etiquetas_raiz",
            "usuario_id",
            text(
                "COALESCE(categoria_id, "
                "'00000000-0000-0000-0000-000000000000'::uuid)"
            ),
            text("lower(nombre)"),
            unique=True,
            postgresql_where=text("padre_id IS NULL"),
        ),
        Index(
            "uq_etiquetas_hija",
            "usuario_id",
            "padre_id",
            text("lower(nombre)"),
            unique=True,
            postgresql_where=text("padre_id IS NOT NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    usuario_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True
    )
    categoria_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("categorias.id", ondelete="CASCADE"), nullable=True, index=True
    )
    nombre: Mapped[str] = mapped_column(String(60), nullable=False)
    color: Mapped[str | None] = mapped_column(String(20), nullable=True)
    padre_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("etiquetas.id", ondelete="CASCADE"), nullable=True
    )
    creada_en: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=_ahora)


class Extracto(Base):
    """Extracto de tarjeta de crédito o de cuenta, leído de un PDF o un Excel.

    Guarda **los números que el propio extracto declara** (periodo, corte, pago,
    cupo, desglose) y, en `extracto_movimientos`, el detalle. Esos números son la
    fuente de verdad para conciliar: si el detalle no cuadra con ellos, algo se leyó
    mal y hay que revisarlo **antes** de importar nada.

    `tipo` y `formato` son texto validado en Python y no un ENUM de PostgreSQL a
    propósito: son listas que crecerán (más bancos, más formatos) y añadir un valor a
    un ENUM es fácil pero quitarlo no existe (ver la nota del `0019`).
    """

    __tablename__ = "extractos"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    usuario_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # A qué cuenta o tarjeta pertenece (puede quedar sin asignar hasta que el usuario la elija)
    cuenta_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("cuentas.id", ondelete="SET NULL"), nullable=True, index=True
    )
    tarjeta_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("tarjetas.id", ondelete="SET NULL"), nullable=True, index=True
    )

    tipo: Mapped[str] = mapped_column(String(10), nullable=False, default="tarjeta")  # tarjeta | cuenta
    formato: Mapped[str] = mapped_column(String(10), nullable=False, default="pdf")  # pdf | xlsx | csv
    banco: Mapped[str | None] = mapped_column(String(60), nullable=True)
    nombre_archivo: Mapped[str] = mapped_column(String(255), nullable=False)
    # Moneda del extracto; sus movimientos pueden estar en otras (`moneda` por fila)
    moneda: Mapped[str] = mapped_column(ForeignKey("monedas.codigo"), nullable=False, default="COP")

    # Periodo y fechas que declara el extracto
    periodo_desde: Mapped[date | None] = mapped_column(Date, nullable=True)
    periodo_hasta: Mapped[date | None] = mapped_column(Date, nullable=True)
    fecha_corte: Mapped[date | None] = mapped_column(Date, nullable=True)
    fecha_pago: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Desglose del corte (lo que dice el extracto, no lo que calculamos)
    saldo_anterior: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    compras: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    intereses: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    intereses_mora: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    otros_cargos: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    abonos: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    pago_total: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    pago_minimo: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    cupo_total: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    cupo_disponible: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    # Lo que el corte declara como usado (`Has utilizado:`), para poder comprobarlo
    cupo_utilizado: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    # La tasa que cobra el banco, como **fracción** (0,2630 = 26,30 % E.A.), igual que en
    # `tarjetas`: así el simulador usa la tasa real del extracto y no una configurada
    tasa_mv: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    tasa_ea: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)

    # Resultado de la conciliación: si no cuadra, se revisa antes de importar
    conciliacion_ok: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Texto extraído (o el volcado del Excel) para poder re-parsear sin volver a subir
    texto_extraido: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Avisos y comprobaciones en JSON (lista de {nombre, calculado, declarado, ok, diferencia})
    conciliacion: Mapped[str | None] = mapped_column(Text, nullable=True)

    creado_en: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=_ahora)


class ExtractoMovimiento(Base):
    """Un renglón del extracto, tal como lo declara el banco.

    Guarda también el **monto original y la tasa de cambio** cuando la compra fue en
    otra moneda: el extracto trae los dos (`$108.515,31` y `25,87 USD` a `4.193,84`), y
    esa es la tasa que se pagó de verdad, no la de hoy.
    """

    __tablename__ = "extracto_movimientos"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    extracto_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("extractos.id", ondelete="CASCADE"), nullable=False, index=True
    )
    usuario_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True
    )
    orden: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    fecha: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    descripcion: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    # Con signo: negativo = plata que entra o se abona a la tarjeta
    valor: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    moneda: Mapped[str] = mapped_column(ForeignKey("monedas.codigo"), nullable=False, default="COP")
    saldo: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)

    # Compra en otra moneda: los dos importes y la tasa que aplicó el banco
    monto_original: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    moneda_original: Mapped[str | None] = mapped_column(String(3), nullable=True)
    tasa_cambio: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)

    # Cuotas (una compra diferida no es una suscripción: `cuotas_total > 1` lo delata)
    cuotas_n: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cuotas_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cuota_mes: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    valor_pendiente: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    # Tasa de esa compra (fracción). El extracto de Davivienda la trae por fila
    tasa_ea: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    titular: Mapped[str | None] = mapped_column(String(2), nullable=True)  # T titular, A adicional

    # Clasificación (Fase 1 la deduce; Fase 2 la usa para importar)
    tipo: Mapped[str] = mapped_column(String(20), nullable=False, default="otro")
    categoria_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("categorias.id", ondelete="SET NULL"), nullable=True
    )
    etiqueta_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("etiquetas.id", ondelete="SET NULL"), nullable=True
    )
    origen: Mapped[str] = mapped_column(String(20), nullable=False, default="sin_clasificar")
    # Un renglón informativo (cuotas anteriores al periodo) no se importa como gasto nuevo
    es_informativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Lo rellena la Fase 2 al importarlo
    transaccion_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("transacciones.id", ondelete="SET NULL"), nullable=True
    )


class Factura(Base):
    """Factura en PDF subida por el usuario, con datos extraídos (texto/monto/fecha)."""

    __tablename__ = "facturas"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    usuario_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True
    )
    nombre_archivo: Mapped[str] = mapped_column(String(255), nullable=False)
    texto_extraido: Mapped[str | None] = mapped_column(Text, nullable=True)
    monto_detectado: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    fecha_detectada: Mapped[date | None] = mapped_column(Date, nullable=True)
    transaccion_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("transacciones.id", ondelete="SET NULL"), nullable=True
    )
    # Bloque tributario de la factura (migración 0029)
    impuestos_total: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    iva_valor: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    descuento: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    impuestos_detalle: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Del QR de la factura electrónica (migración 0031)
    cude: Mapped[str | None] = mapped_column(String(96), nullable=True, index=True)
    url_dian: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # Quién emitió el documento: es lo que une las facturas de un mismo emisor para aprender su
    # formato (`nit:8903990034` o `nombre:CONSORCIO EMCALI`)
    emisor: Mapped[str | None] = mapped_column(String(140), nullable=True)
    emisor_nombre: Mapped[str | None] = mapped_column(String(140), nullable=True)
    # El archivo original, guardado con retención limitada para poder releerlo (con IA) y
    # borrado solo. `archivo_clave` es la referencia en el almacén, no el contenido.
    archivo_clave: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)
    archivo_tipo: Mapped[str | None] = mapped_column(String(80), nullable=True)
    archivo_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    archivo_expira_en: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True, index=True
    )
    # Se releyó con el modelo de visión (alimenta el panel de calidad)
    leida_con_ia: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    # Calidad de la lectura: si hubo que corregirla y si salió bien gracias a una plantilla
    # aprendida (es lo que alimenta el panel de calidad por emisor)
    corregida_en: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    leida_con_plantilla: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    creada_en: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=_ahora)


class FacturaLinea(Base):
    """Un artículo detectado por OCR dentro de una factura.

    Una factura pasa de 1 a N transacciones: cada línea confirmada crea la suya.
    """

    __tablename__ = "factura_lineas"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    factura_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("facturas.id", ondelete="CASCADE"), nullable=False, index=True
    )
    descripcion: Mapped[str] = mapped_column(String(200), nullable=False)
    cantidad: Mapped[Decimal | None] = mapped_column(Numeric(12, 3), nullable=True)
    valor_unitario: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    valor_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    etiqueta_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("etiquetas.id", ondelete="SET NULL"), nullable=True
    )
    # historial | diccionario | embeddings | manual | sin_clasificar
    origen: Mapped[str] = mapped_column(String(20), nullable=False, default="sin_clasificar")
    confianza: Mapped[Decimal | None] = mapped_column(Numeric(4, 3), nullable=True)
    orden: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    transaccion_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("transacciones.id", ondelete="SET NULL"), nullable=True
    )
    # Tratamiento fiscal del artículo según la marca de la factura (migración 0029):
    # `*` gravado, `**` exento, sin marca excluido
    iva_tipo: Mapped[str | None] = mapped_column(String(10), nullable=True)
    creada_en: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=_ahora)


class Plan(Base):
    """Un plan de la app: lo que se paga y lo que incluye.

    Es **catálogo**, no código: los límites se cambian desde la base (o desde un panel) sin
    tocar la aplicación. El precio va en pesos; el coste de los tokens es aparte y se mide.
    """

    __tablename__ = "planes"

    codigo: Mapped[str] = mapped_column(String(24), primary_key=True)
    nombre: Mapped[str] = mapped_column(String(60), nullable=False)
    precio_mes: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    # Lo que incluye cada mes (0 = no incluido)
    lecturas_ia: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    consultas_asistente: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    # Almacenamiento incluido: cuántos archivos guardados a la vez, cuántos días se guarda cada
    # uno y cuánto peso. `archivos_incluidos` en NULL = ilimitado (planes «sin límite»).
    archivos_incluidos: Mapped[int | None] = mapped_column(Integer, nullable=True)
    retencion_dias: Mapped[int] = mapped_column(Integer, nullable=False, default=7, server_default="7")
    almacenamiento_mb: Mapped[int] = mapped_column(
        Integer, nullable=False, default=60, server_default="60"
    )
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    orden: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")


class Propuesta(Base):
    """Algo que el asistente propone hacer y **todavía no ha hecho**.

    El asistente no ejecuta nada: deja la propuesta aquí, con los datos ya resueltos y validados, y
    el usuario confirma en la pantalla. Guardar los datos resueltos (la categoría de verdad, no el
    nombre que dijo el modelo) es lo que garantiza que se ejecute **exactamente** lo que se mostró.
    """

    __tablename__ = "propuestas"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    usuario_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False
    )
    # registrar_movimiento | etiquetar_movimiento
    tipo: Mapped[str] = mapped_column(String(32), nullable=False)
    # Lo que se va a ejecutar, ya resuelto (ids incluidos)
    datos: Mapped[str] = mapped_column(Text, nullable=False)
    # La frase que ve el usuario antes de confirmar
    resumen: Mapped[str] = mapped_column(Text, nullable=False)
    # pendiente | confirmada | rechazada | expirada | fallida
    estado: Mapped[str] = mapped_column(
        String(16), nullable=False, default="pendiente", server_default="pendiente"
    )
    # Qué pasó al ejecutarla (o por qué falló)
    resultado: Mapped[str | None] = mapped_column(Text, nullable=True)
    creada_en: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    resuelta_en: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)


class PaqueteLecturas(Base):
    """Un paquete de lecturas con IA que se compra aparte del plan.

    Es catálogo, como los planes: los precios y las cantidades se cambian en la base. Sirve para
    el que se queda sin lecturas y no quiere (o no puede todavía) subir de plan.
    """

    __tablename__ = "paquetes_lecturas"

    codigo: Mapped[str] = mapped_column(String(24), primary_key=True)
    nombre: Mapped[str] = mapped_column(String(60), nullable=False)
    lecturas: Mapped[int] = mapped_column(Integer, nullable=False)
    precio: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    orden: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")


class Pago(Base):
    """Un intento de compra: un plan o un paquete de lecturas.

    `referencia` es la llave de idempotencia: viaja a la pasarela y vuelve en su aviso, así que un
    aviso repetido no puede acreditar dos veces. `aplicado` lo confirma: cuando está en True, el
    saldo o el plan ya se actualizaron y no se vuelven a tocar.
    """

    __tablename__ = "pagos"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    usuario_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False
    )
    # La restricción única ya crea su índice: es la llave con la que la pasarela avisa
    referencia: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    # plan | paquete
    tipo: Mapped[str] = mapped_column(String(16), nullable=False)
    codigo: Mapped[str] = mapped_column(String(24), nullable=False)
    monto: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    moneda: Mapped[str] = mapped_column(String(3), nullable=False, default="COP", server_default="COP")
    # pendiente | pagado | fallido
    estado: Mapped[str] = mapped_column(
        String(16), nullable=False, default="pendiente", server_default="pendiente"
    )
    pasarela: Mapped[str] = mapped_column(String(24), nullable=False, default="simulada", server_default="simulada")
    id_externo: Mapped[str | None] = mapped_column(String(120), nullable=True)
    # Si el saldo o el plan ya se acreditaron (la garantía contra el doble cobro)
    aplicado: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    detalle: Mapped[str | None] = mapped_column(Text, nullable=True)
    creado_en: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    pagado_en: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)


class ConsumoIa(Base):
    """Lo que un usuario gastó en el mes: IA **y almacenamiento**.

    De la IA se guardan las lecturas, las consultas, los tokens y el coste real (para mirar el
    margen de cada plan). del almacenamiento se guarda el **MB-día**: cada día, lo que ocupan sus
    archivos se suma al mes. Es la métrica honesta para cobrar espacio, porque no es lo mismo
    guardar 30 archivos siete días que treinta días.
    """

    __tablename__ = "consumos_ia"

    __table_args__ = (
        UniqueConstraint("usuario_id", "periodo", name="uq_consumos_ia_periodo"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    usuario_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False
    )
    # "2026-09", en la zona del usuario (no en UTC: el mes es el del usuario)
    periodo: Mapped[str] = mapped_column(String(7), nullable=False)
    lecturas: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    consultas: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    tokens_entrada: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    tokens_salida: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    # Coste real facturado por el proveedor, en dólares (para vigilar el margen)
    costo_usd: Mapped[Decimal] = mapped_column(
        Numeric(12, 6), nullable=False, default=0, server_default="0"
    )
    actualizado_en: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()"),
        onupdate=lambda: datetime.now(UTC),
    )

    # ── Almacenamiento (la suma del día a día, no una foto) ─────────────────────────────
    # `archivos_dia` y `mb_dia` son sumas diarias: divididas por los días medidos dan el
    # promedio, y con eso se sabe lo que cuesta de verdad el espacio de cada cliente.
    archivos_dia: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    mb_dia: Mapped[Decimal] = mapped_column(
        Numeric(14, 3), nullable=False, default=0, server_default="0"
    )
    # Último día medido: evita contar dos veces si el trabajo corre dos veces el mismo día
    ultima_medicion: Mapped[date | None] = mapped_column(Date, nullable=True)
    dias_medidos: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")


class ConsultaAsistente(Base):
    """Una pregunta al asistente: qué se preguntó, qué herramientas se usaron y qué costó.

    Se guarda para poder auditar y para el informe de promedios. **No** se guarda la respuesta
    entera: con la pregunta y las herramientas basta para saber por dónde fue.
    """

    __tablename__ = "consultas_asistente"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    usuario_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False
    )
    pregunta: Mapped[str] = mapped_column(Text, nullable=False)
    herramientas: Mapped[str | None] = mapped_column(Text, nullable=True)
    tokens_entrada: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    tokens_salida: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    costo_usd: Mapped[Decimal] = mapped_column(
        Numeric(12, 6), nullable=False, default=0, server_default="0"
    )
    creada_en: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )


class CasoLector(Base):
    """Un documento que el lector leyó mal, tal como lo vio el usuario.

    Es el buzón de casos: no se puede ir a cada establecimiento a pedirle un formato, pero sí se
    puede **acumular** lo que falla. El caso guarda el texto, lo que el lector dijo, lo que el
    usuario dejó al final y —solo si lo autoriza— el archivo. De ahí sale una tarea del backlog y,
    al arreglarla, un test que impide que se rompa otra vez.
    """

    __tablename__ = "casos_lector"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    usuario_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False
    )
    # La factura puede borrarse después: el caso se queda (es el aprendizaje, no el documento)
    factura_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("facturas.id", ondelete="SET NULL"), nullable=True
    )
    emisor: Mapped[str | None] = mapped_column(String(140), nullable=True)
    emisor_nombre: Mapped[str | None] = mapped_column(String(140), nullable=True)
    texto: Mapped[str] = mapped_column(Text, nullable=False)
    tipo_documento: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # Lo que dijo el lector sobre este texto…
    monto_leido: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    fecha_leida: Mapped[date | None] = mapped_column(Date, nullable=True)
    # …y con qué se quedó el usuario
    monto_corregido: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    fecha_corregida: Mapped[date | None] = mapped_column(Date, nullable=True)
    motivo: Mapped[str | None] = mapped_column(String(300), nullable=True)
    # El archivo original, solo si el usuario lo autoriza (para poder reproducir el fallo)
    archivo: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    archivo_nombre: Mapped[str | None] = mapped_column(String(200), nullable=True)
    archivo_tipo: Mapped[str | None] = mapped_column(String(80), nullable=True)
    estado: Mapped[str] = mapped_column(String(16), nullable=False, default="abierto", server_default="abierto")
    creado_en: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    resuelto_en: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)


class PatronIgnorado(Base):
    """Renglones que el usuario borra **siempre**: no son artículos.

    Un recibo trae «Nit: 900123456», «Cajero: 12» o «Cambio: 0» entre los renglones, y el lector
    los puede tomar por productos. Cuando el usuario los borra, se guarda el patrón; a la segunda
    vez se descartan solos (una vez podría ser un error, «siempre» es un patrón).
    """

    __tablename__ = "patrones_ignorados"

    __table_args__ = (
        UniqueConstraint("usuario_id", "patron", name="uq_patrones_ignorados_patron"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    usuario_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False
    )
    # Texto normalizado del renglón, sin números ni códigos: «CAJERO», «NIT», «CAMBIO»
    patron: Mapped[str] = mapped_column(String(80), nullable=False)
    # Un ejemplo de lo que se borró, para que el usuario reconozca de qué se trata
    ejemplo: Mapped[str] = mapped_column(String(120), nullable=False)
    veces: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    creada_en: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    actualizada_en: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()"),
        onupdate=lambda: datetime.now(UTC),
    )


class PlantillaLector(Base):
    """Aprendizaje por **emisor**: dónde está el total y la fecha en sus documentos.

    No se puede ir a cada banco o establecimiento a pedirles un formato, pero la app sí puede
    aprenderse el de cada uno: cuando el usuario corrige el monto de un documento de EMCALI, se
    guarda que en esos documentos el total va en la línea que dice «VALOR DEL PAGO», y la
    próxima factura de EMCALI sale bien a la primera.
    """

    __tablename__ = "plantillas_lector"

    __table_args__ = (
        UniqueConstraint("usuario_id", "emisor", name="uq_plantillas_lector_emisor"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    usuario_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False
    )
    # Clave estable del emisor: `nit:8903990034` o `nombre:GASES DE OCCIDENTE`
    emisor: Mapped[str] = mapped_column(String(140), nullable=False)
    # Cómo mostrarlo: «Gases de Occidente»
    nombre: Mapped[str] = mapped_column(String(140), nullable=False)
    # Lo aprendido: la etiqueta que lleva el total, la que lleva la fecha y el tipo
    campo_monto: Mapped[str | None] = mapped_column(String(40), nullable=True)
    campo_fecha: Mapped[str | None] = mapped_column(String(40), nullable=True)
    tipo_documento: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # Cuántas veces ha servido (para que el usuario vea cuáles valen la pena)
    usos: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    creada_en: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    actualizada_en: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()"),
        onupdate=lambda: datetime.now(UTC),
    )


class ReglaOcr(Base):
    """Aprendizaje: «este artículo va siempre a esta etiqueta»."""

    __tablename__ = "reglas_ocr"

    # Una sola regla por (usuario, patrón): la migración 0016 crea esta unicidad.
    __table_args__ = (
        UniqueConstraint("usuario_id", "patron", name="uq_reglas_ocr_patron"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    usuario_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False
    )
    # Descripción normalizada (mayúsculas, sin acentos ni códigos) para emparejar
    patron: Mapped[str] = mapped_column(String(120), nullable=False)
    etiqueta_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("etiquetas.id", ondelete="CASCADE"), nullable=False
    )
    veces_usada: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    creada_en: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=_ahora)
    actualizada_en: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=_ahora)


class Presupuesto(Base):
    """Límite de gasto mensual por categoría."""

    __tablename__ = "presupuestos"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    usuario_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True
    )
    categoria_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("categorias.id", ondelete="CASCADE"), nullable=False
    )
    monto_limite: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    moneda: Mapped[str] = mapped_column(ForeignKey("monedas.codigo"), nullable=False, default="COP")
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    creada_en: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=_ahora)


class Producto(Base):
    """Producto del catálogo de mercado."""

    __tablename__ = "productos"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    usuario_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True
    )
    nombre: Mapped[str] = mapped_column(String(120), nullable=False)
    unidad: Mapped[str | None] = mapped_column(String(20), nullable=True)
    creada_en: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=_ahora)


class PrecioMercado(Base):
    """Precio histórico de un producto en una tienda."""

    __tablename__ = "precios_mercado"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    usuario_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True
    )
    producto_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("productos.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tienda: Mapped[str | None] = mapped_column(String(80), nullable=True)
    precio: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    moneda: Mapped[str] = mapped_column(ForeignKey("monedas.codigo"), nullable=False, default="COP")
    fecha: Mapped[date] = mapped_column(Date, nullable=False, default=_ahora)


class ItemLista(Base):
    """Item de la lista de mercado."""

    __tablename__ = "lista_mercado"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    usuario_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True
    )
    producto_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("productos.id", ondelete="SET NULL"), nullable=True
    )
    nombre: Mapped[str] = mapped_column(String(120), nullable=False)
    cantidad: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=Decimal("1"))
    precio_estimado: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    comprado: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    creada_en: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=_ahora)


class MetaAhorro(Base):
    """Meta de ahorro (se nutre de aportes)."""

    __tablename__ = "metas_ahorro"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    usuario_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True
    )
    nombre: Mapped[str] = mapped_column(String(120), nullable=False)
    monto_objetivo: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    moneda: Mapped[str] = mapped_column(ForeignKey("monedas.codigo"), nullable=False, default="COP")
    fecha_limite: Mapped[date | None] = mapped_column(Date, nullable=True)
    notas: Mapped[str | None] = mapped_column(Text, nullable=True)
    creada_en: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=_ahora)


class AporteMeta(Base):
    """Aporte a una meta de ahorro."""

    __tablename__ = "aportes_meta"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    usuario_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True
    )
    meta_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("metas_ahorro.id", ondelete="CASCADE"), nullable=False, index=True
    )
    monto: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    fecha: Mapped[date] = mapped_column(Date, nullable=False, default=_ahora)
    notas: Mapped[str | None] = mapped_column(String(255), nullable=True)
    creada_en: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=_ahora)


class Cuenta(Base):
    """Cuenta de dinero (efectivo, banco, ahorros…) con saldo inicial.

    El saldo actual es `saldo_inicial + ingresos - gastos` de esa cuenta.
    """

    __tablename__ = "cuentas"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    usuario_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True
    )
    nombre: Mapped[str] = mapped_column(String(80), nullable=False)
    tipo: Mapped[str] = mapped_column(String(20), nullable=False, default="efectivo")
    saldo_inicial: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0"))
    moneda: Mapped[str] = mapped_column(ForeignKey("monedas.codigo"), nullable=False, default="COP")
    activa: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    creada_en: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=_ahora)


class ConfigNotificaciones(Base):
    """Preferencias de notificación de alarmas de pago por usuario."""

    __tablename__ = "config_notificaciones"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    usuario_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    canal: Mapped[str] = mapped_column(String(20), nullable=False, default="telegram")  # telegram|email|whatsapp|ambos|todos
    telegram_chat_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Número de WhatsApp en formato internacional sin '+' (ej. 573001234567)
    whatsapp_numero: Mapped[str | None] = mapped_column(String(20), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    dias_anticipacion: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    ultima_notificacion: Mapped[date | None] = mapped_column(Date, nullable=True)
    creada_en: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=_ahora)


class DeudaTarjeta(Base):
    """Saldo deudor de una tarjeta en una moneda (lo que dice el extracto).

    Una tarjeta puede tener deuda en varias monedas (ej. COP y USD).
    """

    __tablename__ = "deudas_tarjeta"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    usuario_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tarjeta_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tarjetas.id", ondelete="CASCADE"), nullable=False, index=True
    )
    moneda: Mapped[str] = mapped_column(ForeignKey("monedas.codigo"), nullable=False, default="COP")
    monto: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    fecha: Mapped[date] = mapped_column(Date, nullable=False, default=_ahora)
    notas: Mapped[str | None] = mapped_column(String(255), nullable=True)
    creada_en: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=_ahora)


class PagoTarjeta(Base):
    """Pago de la deuda de una tarjeta de crédito: baja la cuenta **y** la deuda.

    Es un **flujo**, al contrario que `DeudaTarjeta` (que es un nivel: lo que dice el
    extracto). La deuda vigente es el último extracto de cada moneda menos los pagos
    posteriores a su fecha; cuando llegue el extracto siguiente, que ya incluye el
    pago, este deja de restarse y no se cuenta dos veces.

    Cada pago tiene su transacción de tipo **transferencia** (de la cuenta a la
    tarjeta): mover dinero a pagar una deuda propia **no es un gasto**, así que no
    aparece en los reportes por categoría ni en el flujo de caja — si fuera un gasto,
    el consumo se contaría dos veces (al comprar y al pagar).
    """

    __tablename__ = "pagos_tarjeta"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    usuario_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tarjeta_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tarjetas.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # De qué cuenta salió el dinero
    cuenta_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("cuentas.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # El movimiento que lo refleja (transferencia de la cuenta a la tarjeta)
    transaccion_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("transacciones.id", ondelete="SET NULL"), nullable=True
    )
    monto: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    moneda: Mapped[str] = mapped_column(ForeignKey("monedas.codigo"), nullable=False, default="COP")
    fecha: Mapped[date] = mapped_column(Date, nullable=False, default=_ahora, index=True)
    notas: Mapped[str | None] = mapped_column(String(255), nullable=True)
    creada_en: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=_ahora)


class Poliza(Base):
    """Seguro: de vida, salud, vehículo, hogar… (personas y/o bienes).

    Es un compromiso recurrente como una suscripción: tiene prima, periodicidad y
    `proximo_pago`, y el scheduler genera el gasto al vencer. Además lleva la
    **vigencia** (inicio/fin) para avisar del vencimiento y la renovación, y los
    datos del **bien asegurado** cuando es un vehículo (placa, marca, modelo).

    Una póliza cubre a una persona (`asegurado_nombre`) o a un bien (los campos de
    vehículo); los beneficiarios con su porcentaje viven en `beneficiarios`.
    """

    __tablename__ = "polizas"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    usuario_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # vida | salud | vehiculo | hogar | otro
    tipo: Mapped[str] = mapped_column(String(20), nullable=False, default="vida")
    aseguradora: Mapped[str] = mapped_column(String(120), nullable=False)
    numero_poliza: Mapped[str | None] = mapped_column(String(60), nullable=True)
    # Persona asegurada (vida/salud/hogar). Para vehículo, el tomador/propietario.
    asegurado_nombre: Mapped[str | None] = mapped_column(String(120), nullable=True)

    # Bien asegurado (vehículo)
    placa: Mapped[str | None] = mapped_column(String(10), nullable=True)
    marca: Mapped[str | None] = mapped_column(String(60), nullable=True)
    modelo: Mapped[str | None] = mapped_column(String(60), nullable=True)
    anio: Mapped[int | None] = mapped_column(Integer, nullable=True)
    valor_asegurado: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)

    # Prima (lo que se paga) y cada cuánto
    prima: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    moneda: Mapped[str] = mapped_column(ForeignKey("monedas.codigo"), nullable=False, default="COP")
    periodicidad: Mapped[Periodicidad] = mapped_column(_periodicidad, nullable=False, default=Periodicidad.MENSUAL)

    # Vigencia y próximo cobro
    fecha_inicio: Mapped[date | None] = mapped_column(Date, nullable=True)
    fecha_fin: Mapped[date | None] = mapped_column(Date, nullable=True)
    proximo_pago: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    renovacion_automatica: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Igual que una suscripción: el cargo cae en el árbol y puede ir a una tarjeta
    categoria_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("categorias.id", ondelete="SET NULL"), nullable=True
    )
    etiqueta_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("etiquetas.id", ondelete="SET NULL"), nullable=True
    )
    tarjeta_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("tarjetas.id", ondelete="SET NULL"), nullable=True
    )
    cuenta_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("cuentas.id", ondelete="SET NULL"), nullable=True
    )
    # Reutiliza el vocabulario activa | pausada | cancelada de las suscripciones
    estado: Mapped[EstadoSuscripcion] = mapped_column(
        _estado_suscripcion, nullable=False, default=EstadoSuscripcion.ACTIVA
    )
    notas: Mapped[str | None] = mapped_column(Text, nullable=True)
    creada_en: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=_ahora)

    @property
    def titulo(self) -> str:
        """Etiqueta legible de la póliza: «Vehículo ABC123 (Sura)»."""
        if self.tipo == "vehiculo" and self.placa:
            return f"Vehículo {self.placa} ({self.aseguradora})"
        quien = self.asegurado_nombre or self.tipo.capitalize()
        return f"{quien} ({self.aseguradora})"


class Beneficiario(Base):
    """Beneficiario de una póliza (típicamente de vida) con su porcentaje."""

    __tablename__ = "beneficiarios"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    usuario_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True
    )
    poliza_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("polizas.id", ondelete="CASCADE"), nullable=False, index=True
    )
    nombre: Mapped[str] = mapped_column(String(120), nullable=False)
    parentesco: Mapped[str | None] = mapped_column(String(60), nullable=True)
    # Porcentaje de la indemnización (0-100). NULL = sin reparto definido.
    porcentaje: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    creada_en: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=_ahora)


class PolizaAsegurado(Base):
    """Persona cubierta por una póliza (una póliza familiar cubre a varias).

    `Poliza.asegurado_nombre` sigue siendo la persona asegurada **principal**
    (para vida/salud/hogar) o el tomador (vehículo), y sirve para el título. Esta
    tabla es el detalle: quiénes están cubiertos, con qué parentesco y desde
    cuándo, y cuál de ellos es el titular (`es_titular`).
    """

    __tablename__ = "poliza_asegurados"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    usuario_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True
    )
    poliza_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("polizas.id", ondelete="CASCADE"), nullable=False, index=True
    )
    nombre: Mapped[str] = mapped_column(String(120), nullable=False)
    parentesco: Mapped[str | None] = mapped_column(String(60), nullable=True)
    fecha_nacimiento: Mapped[date | None] = mapped_column(Date, nullable=True)
    # Solo uno por póliza: el asegurado principal
    es_titular: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    creada_en: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=_ahora)
