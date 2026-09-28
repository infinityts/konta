"""Modelos del núcleo de Finly (multi-usuario, multi-moneda).

El esquema real lo crea Alembic (alembic/versions/0001_nucleo.py). Estos modelos
son el espejo ORM. Convenciones: UUID vía aplicación, montos con Numeric(14,2),
monedas como código ISO (CHAR(3)) referenciando `monedas`.
"""

from __future__ import annotations

import enum
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import Boolean, Date, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID, ENUM as PG_ENUM
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


def _ahora() -> datetime:
    return datetime.now(timezone.utc)


# --- Vocabulario congelado (coincide con la migración 0001) ---


class TipoCategoria(str, enum.Enum):
    INGRESO = "ingreso"
    GASTO = "gasto"


class Periodicidad(str, enum.Enum):
    SEMANAL = "semanal"
    MENSUAL = "mensual"
    TRIMESTRAL = "trimestral"
    ANUAL = "anual"


class EstadoSuscripcion(str, enum.Enum):
    ACTIVA = "activa"
    PAUSADA = "pausada"
    CANCELADA = "cancelada"


class TipoTarjeta(str, enum.Enum):
    CREDITO = "credito"
    DEBITO = "debito"


class TipoTransaccion(str, enum.Enum):
    INGRESO = "ingreso"
    GASTO = "gasto"


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


class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    nombre: Mapped[str] = mapped_column(String(120), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
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
    etiqueta_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("etiquetas.id", ondelete="SET NULL"), nullable=True
    )
    notas: Mapped[str | None] = mapped_column(Text, nullable=True)


class PeriodicidadIngreso(str, enum.Enum):
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
    activa: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    creada_en: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=_ahora)


class Etiqueta(Base):
    """Etiquetas y subetiquetas (autojerárquica).

    `padre_id` es NULL para una etiqueta raíz y apunta a otra etiqueta para una
    subetiqueta. Una transacción puede asociarse a una etiqueta (raíz o sub).
    """

    __tablename__ = "etiquetas"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    usuario_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True
    )
    nombre: Mapped[str] = mapped_column(String(60), nullable=False)
    color: Mapped[str | None] = mapped_column(String(20), nullable=True)
    padre_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("etiquetas.id", ondelete="CASCADE"), nullable=True
    )
    creada_en: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=_ahora)


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
    creada_en: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=_ahora)
