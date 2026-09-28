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

from sqlalchemy import (
    Boolean,
    Date,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
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
    SEMESTRAL = "semestral"
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
    cuenta_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("cuentas.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # Gasto generado por una póliza (como `suscripcion_id` para las suscripciones)
    poliza_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("polizas.id", ondelete="SET NULL"), nullable=True, index=True
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
    creada_en: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=_ahora)


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
