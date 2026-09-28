"""Esquemas Pydantic (entradas/salidas de la API)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

from .models import (
    EstadoSuscripcion,
    Periodicidad,
    PeriodicidadIngreso,
    TipoCategoria,
    TipoTarjeta,
    TipoTransaccion,
)


# --- auth ---


class UserCreate(BaseModel):
    email: EmailStr
    nombre: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=8)
    moneda_principal: str = "COP"


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    nombre: str
    moneda_principal: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


# --- categorias ---


class CategoriaIn(BaseModel):
    nombre: str = Field(min_length=1, max_length=80)
    tipo: TipoCategoria
    icono: str | None = None
    color: str | None = None


class CategoriaUpdate(BaseModel):
    nombre: str | None = None
    tipo: TipoCategoria | None = None
    icono: str | None = None
    color: str | None = None


class CategoriaOut(CategoriaIn):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    usuario_id: uuid.UUID


# --- tarjetas ---


class TarjetaIn(BaseModel):
    nombre: str = Field(min_length=1, max_length=80)
    banco: str | None = None
    tipo: TipoTarjeta
    moneda: str = "COP"
    dia_corte: int | None = Field(None, ge=1, le=31)
    dia_pago: int | None = Field(None, ge=1, le=31)
    limite: Decimal | None = Field(None, ge=0)
    tasa_interes: Decimal | None = Field(None, ge=0)
    tasa_interes_ea: Decimal | None = Field(None, ge=0)
    cuenta_id: uuid.UUID | None = None
    activa: bool = True


class TarjetaUpdate(BaseModel):
    nombre: str | None = None
    banco: str | None = None
    tipo: TipoTarjeta | None = None
    moneda: str | None = None
    dia_corte: int | None = Field(None, ge=1, le=31)
    dia_pago: int | None = Field(None, ge=1, le=31)
    limite: Decimal | None = Field(None, ge=0)
    tasa_interes: Decimal | None = Field(None, ge=0)
    tasa_interes_ea: Decimal | None = Field(None, ge=0)
    cuenta_id: uuid.UUID | None = None
    activa: bool | None = None


class TarjetaOut(TarjetaIn):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    usuario_id: uuid.UUID


class DeudaIn(BaseModel):
    moneda: str = "COP"
    monto: Decimal = Field(gt=0)
    fecha: date | None = None
    notas: str | None = None


class DeudaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tarjeta_id: uuid.UUID
    moneda: str
    monto: Decimal
    fecha: date
    notas: str | None


class TarjetaConDeudaOut(TarjetaOut):
    """Tarjeta con su deuda (por moneda y total convertido a COP si hay tasa)."""

    deudas: list[DeudaOut] = []
    deuda_por_moneda: dict[str, float] = {}
    deuda_total_cop: float | None = None
    cuenta_nombre: str | None = None


# --- suscripciones ---


class SuscripcionIn(BaseModel):
    nombre: str = Field(min_length=1, max_length=120)
    monto: Decimal = Field(gt=0)
    moneda: str = "COP"
    periodicidad: Periodicidad = Periodicidad.MENSUAL
    fecha_inicio: date | None = None
    proximo_pago: date | None = None
    categoria_id: uuid.UUID | None = None
    tarjeta_id: uuid.UUID | None = None
    etiqueta_id: uuid.UUID | None = None
    estado: EstadoSuscripcion = EstadoSuscripcion.ACTIVA
    notas: str | None = None


class SuscripcionUpdate(BaseModel):
    nombre: str | None = None
    monto: Decimal | None = Field(None, gt=0)
    moneda: str | None = None
    periodicidad: Periodicidad | None = None
    fecha_inicio: date | None = None
    proximo_pago: date | None = None
    categoria_id: uuid.UUID | None = None
    tarjeta_id: uuid.UUID | None = None
    etiqueta_id: uuid.UUID | None = None
    estado: EstadoSuscripcion | None = None
    notas: str | None = None


class SuscripcionOut(SuscripcionIn):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    usuario_id: uuid.UUID


# --- transacciones ---


class TransaccionIn(BaseModel):
    tipo: TipoTransaccion
    monto: Decimal = Field(gt=0)
    moneda: str = "COP"
    fecha: date
    descripcion: str | None = None
    categoria_id: uuid.UUID | None = None
    tarjeta_id: uuid.UUID | None = None
    suscripcion_id: uuid.UUID | None = None
    etiqueta_id: uuid.UUID | None = None
    cuenta_id: uuid.UUID | None = None
    notas: str | None = None


class TransaccionUpdate(BaseModel):
    tipo: TipoTransaccion | None = None
    monto: Decimal | None = Field(None, gt=0)
    moneda: str | None = None
    fecha: date | None = None
    descripcion: str | None = None
    categoria_id: uuid.UUID | None = None
    tarjeta_id: uuid.UUID | None = None
    suscripcion_id: uuid.UUID | None = None
    etiqueta_id: uuid.UUID | None = None
    cuenta_id: uuid.UUID | None = None
    notas: str | None = None


class TransaccionOut(TransaccionIn):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    usuario_id: uuid.UUID


# --- ingresos recurrentes ---


class IngresoRecurrenteIn(BaseModel):
    nombre: str = Field(min_length=1, max_length=120)
    monto: Decimal = Field(gt=0)
    moneda: str = "COP"
    periodicidad: PeriodicidadIngreso
    # mensual: 1-31 · semanal: 0 (lunes) a 6 (domingo) · diario: ignorado
    dia: int | None = None
    categoria_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def _validar_dia(self) -> "IngresoRecurrenteIn":
        if self.periodicidad == PeriodicidadIngreso.MENSUAL and not (self.dia is not None and 1 <= self.dia <= 31):
            raise ValueError("Para periodicidad mensual, 'dia' debe estar entre 1 y 31")
        if self.periodicidad == PeriodicidadIngreso.SEMANAL and not (self.dia is not None and 0 <= self.dia <= 6):
            raise ValueError("Para periodicidad semanal, 'dia' debe ser 0 (lunes) a 6 (domingo)")
        return self


class IngresoRecurrenteUpdate(BaseModel):
    nombre: str | None = None
    monto: Decimal | None = Field(None, gt=0)
    moneda: str | None = None
    periodicidad: PeriodicidadIngreso | None = None
    dia: int | None = None
    categoria_id: uuid.UUID | None = None
    activa: bool | None = None


class IngresoRecurrenteOut(IngresoRecurrenteIn):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    usuario_id: uuid.UUID
    proxima_ejecucion: date
    activa: bool


# --- etiquetas y subetiquetas ---


class EtiquetaIn(BaseModel):
    nombre: str = Field(min_length=1, max_length=60)
    color: str | None = None
    # La categoría a la que pertenece la etiqueta
    categoria_id: uuid.UUID | None = None
    # NULL = etiqueta; con valor = subetiqueta de esa etiqueta
    padre_id: uuid.UUID | None = None


class EtiquetaUpdate(BaseModel):
    nombre: str | None = None
    color: str | None = None
    categoria_id: uuid.UUID | None = None
    padre_id: uuid.UUID | None = None


class EtiquetaOut(EtiquetaIn):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    usuario_id: uuid.UUID


# --- alertas ---


class AlertaOut(BaseModel):
    tipo: str  # 'suscripcion' | 'tarjeta_pago' | 'tarjeta_corte'
    titulo: str
    fecha: date
    dias_restantes: int  # negativo = ya vencido
    monto: Decimal | None = None
    moneda: str | None = None


# --- reportes ---


class ReporteMesOut(BaseModel):
    mes: str
    ingresos: float
    gastos: float
    balance: float


class ReporteCategoriaOut(BaseModel):
    categoria: str
    etiqueta: str | None = None
    tipo: str
    total: float


# --- facturas (PDF) ---


class FacturaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    usuario_id: uuid.UUID
    nombre_archivo: str
    texto_extraido: str | None
    monto_detectado: Decimal | None
    fecha_detectada: date | None
    transaccion_id: uuid.UUID | None
    creada_en: datetime


class AsociarFacturaIn(BaseModel):
    transaccion_id: uuid.UUID


# --- líneas de factura (OCR por línea) ---


class FacturaLineaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    factura_id: uuid.UUID
    descripcion: str
    cantidad: Decimal | None
    valor_unitario: Decimal | None
    valor_total: Decimal
    etiqueta_id: uuid.UUID | None
    origen: str  # historial | diccionario | embeddings | manual | sin_clasificar
    confianza: Decimal | None
    orden: int
    transaccion_id: uuid.UUID | None


class FacturaDetalleOut(FacturaOut):
    """Factura con sus líneas detectadas por OCR."""

    lineas: list[FacturaLineaOut] = []
    tipo_documento: str | None = None  # mercado | gasolina | servicios | restaurante | otro


class ParsearLineasIn(BaseModel):
    """`texto` permite re-parsear un texto distinto del guardado (opcional)."""

    texto: str | None = None


class LineaUpdateIn(BaseModel):
    """Editar una línea. `etiqueta_id` corregida se aprende en `reglas_ocr`."""

    descripcion: str | None = None
    valor_total: Decimal | None = Field(default=None, gt=0)
    etiqueta_id: uuid.UUID | None = None


class ConfirmarLineasIn(BaseModel):
    """`linea_ids` vacío o ausente = todas las líneas sin confirmar."""

    linea_ids: list[uuid.UUID] | None = None
    cuenta_id: uuid.UUID | None = None


# --- presupuestos ---


class PresupuestoIn(BaseModel):
    categoria_id: uuid.UUID
    monto_limite: Decimal = Field(gt=0)
    moneda: str = "COP"


class PresupuestoUpdate(BaseModel):
    monto_limite: Decimal | None = Field(None, gt=0)
    moneda: str | None = None
    activo: bool | None = None


class PresupuestoOut(BaseModel):
    id: uuid.UUID
    categoria_id: uuid.UUID
    categoria_nombre: str
    monto_limite: Decimal
    moneda: str
    gastado: float
    restante: float
    porcentaje: float
    activo: bool


# --- importar CSV ---


class ImportarFilaIn(BaseModel):
    fecha: date
    descripcion: str | None = None
    monto: Decimal = Field(gt=0)
    tipo: TipoTransaccion
    moneda: str = "COP"
    categoria_id: uuid.UUID | None = None


class ImportarConfirmarIn(BaseModel):
    filas: list[ImportarFilaIn]


class ImportarPreviewOut(BaseModel):
    filas: list[ImportarFilaIn]
    total: int


class ImportarResultadoOut(BaseModel):
    creadas: int


# --- mercado (productos, precios, lista) ---


class ProductoIn(BaseModel):
    nombre: str = Field(min_length=1, max_length=120)
    unidad: str | None = None


class ProductoUpdate(BaseModel):
    nombre: str | None = None
    unidad: str | None = None


class ProductoOut(ProductoIn):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    usuario_id: uuid.UUID


class PrecioIn(BaseModel):
    tienda: str | None = None
    precio: Decimal = Field(gt=0)
    moneda: str = "COP"
    fecha: date | None = None


class PrecioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    producto_id: uuid.UUID
    tienda: str | None
    precio: Decimal
    moneda: str
    fecha: date


class ComparativoTiendaOut(BaseModel):
    tienda: str
    precio: Decimal
    moneda: str
    fecha: date


class ComparativoOut(BaseModel):
    producto_id: uuid.UUID
    producto_nombre: str
    tiendas: list[ComparativoTiendaOut]
    mas_barata: str | None = None


class ItemListaIn(BaseModel):
    producto_id: uuid.UUID | None = None
    nombre: str = Field(min_length=1, max_length=120)
    cantidad: Decimal = Field(default=Decimal("1"), gt=0)
    precio_estimado: Decimal | None = None


class ItemListaUpdate(BaseModel):
    nombre: str | None = None
    cantidad: Decimal | None = Field(None, gt=0)
    precio_estimado: Decimal | None = None
    comprado: bool | None = None


class ItemListaOut(ItemListaIn):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    usuario_id: uuid.UUID
    comprado: bool


class ListaMercadoOut(BaseModel):
    items: list[ItemListaOut]
    total_estimado: float
    pendientes: int


# --- monedas y tasas de cambio ---


class MonedaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    codigo: str
    nombre: str
    simbolo: str


class TasaIn(BaseModel):
    moneda_origen: str = Field(min_length=3, max_length=3)
    moneda_destino: str = Field(min_length=3, max_length=3)
    tasa: Decimal = Field(gt=0)
    fecha: date | None = None
    fuente: str | None = None


class TasaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    moneda_origen: str
    moneda_destino: str
    tasa: Decimal
    fecha: date
    fuente: str | None


class ConversionOut(BaseModel):
    de: str
    a: str
    monto: Decimal
    tasa: Decimal
    resultado: Decimal


# --- simulador de intereses de tarjeta ---


class SimulacionOut(BaseModel):
    saldo_inicial: Decimal
    tasa_mensual: Decimal
    pago_mensual: Decimal
    meses: int
    total_intereses: Decimal
    total_pagado: Decimal
    viable: bool


# --- proyección de flujo de caja ---


class FlujoMesOut(BaseModel):
    mes: str
    ingresos: float
    gastos_fijos: float
    gastos_variables: float
    gastos: float
    balance: float
    acumulado: float


class FlujoCajaOut(BaseModel):
    meses: list[FlujoMesOut]
    gasto_variable_promedio: float
    total_ingresos: float
    total_gastos: float
    balance_final: float


# --- metas de ahorro ---


class MetaIn(BaseModel):
    nombre: str = Field(min_length=1, max_length=120)
    monto_objetivo: Decimal = Field(gt=0)
    moneda: str = "COP"
    fecha_limite: date | None = None
    notas: str | None = None


class MetaUpdate(BaseModel):
    nombre: str | None = None
    monto_objetivo: Decimal | None = Field(None, gt=0)
    moneda: str | None = None
    fecha_limite: date | None = None
    notas: str | None = None


class AporteIn(BaseModel):
    monto: Decimal = Field(gt=0)
    fecha: date | None = None
    notas: str | None = None


class AporteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    meta_id: uuid.UUID
    monto: Decimal
    fecha: date
    notas: str | None


class MetaOut(BaseModel):
    id: uuid.UUID
    nombre: str
    monto_objetivo: Decimal
    moneda: str
    monto_actual: float
    restante: float
    porcentaje: float
    fecha_limite: date | None
    aporte_mensual_sugerido: float | None
    completada: bool
    notas: str | None


# --- notificaciones (Telegram / email) ---


class NotificacionesIn(BaseModel):
    # `ambos` = telegram + correo (compatibilidad); `todos` = los tres canales.
    canal: Literal["telegram", "email", "whatsapp", "ambos", "todos"] = "telegram"
    telegram_chat_id: str | None = None
    whatsapp_numero: str | None = Field(default=None, max_length=20)
    email: EmailStr | None = None
    dias_anticipacion: int = Field(5, ge=1, le=60)
    activo: bool = False


class NotificacionesOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    canal: str
    telegram_chat_id: str | None
    whatsapp_numero: str | None
    email: str | None
    dias_anticipacion: int
    activo: bool
    ultima_notificacion: date | None


class PruebaNotificacionOut(BaseModel):
    enviados: list[str]
    alertas: int


class ChatTelegramOut(BaseModel):
    chat_id: str
    nombre: str


class DetectarTelegramOut(BaseModel):
    chats: list[ChatTelegramOut]


# --- cuentas, saldos y consolidado ---


class CuentaIn(BaseModel):
    nombre: str = Field(min_length=1, max_length=80)
    tipo: str = "efectivo"
    saldo_inicial: Decimal = Decimal("0")
    moneda: str = "COP"
    activa: bool = True


class CuentaUpdate(BaseModel):
    nombre: str | None = None
    tipo: str | None = None
    saldo_inicial: Decimal | None = None
    moneda: str | None = None
    activa: bool | None = None


class CuentaOut(BaseModel):
    id: uuid.UUID
    nombre: str
    tipo: str
    moneda: str
    activa: bool
    saldo_inicial: Decimal
    ingresos: float
    gastos: float
    saldo_actual: float


class SaldoResumenOut(BaseModel):
    saldo_total: float
    saldo_inicial_total: float
    ingresos_total: float
    gastos_total: float
    sin_cuenta: float
    sin_cuenta_movimientos: int
    sobregirado: bool
    cuentas: list[CuentaOut]


class ConsolidadoMesOut(BaseModel):
    mes: str
    saldo_inicial: float
    ingresos: float
    gastos: float
    balance: float
    saldo_final: float


class ConsolidadoOut(BaseModel):
    meses: list[ConsolidadoMesOut]
    saldo_actual: float


class MotivoOut(BaseModel):
    tipo: str
    etiqueta: str
    monto: float
    detalle: str | None = None


class ProximoIngresoOut(BaseModel):
    nombre: str
    monto: float
    fecha: date


class DiagnosticoOut(BaseModel):
    saldo_actual: float
    sobregirado: bool
    tiene_cuentas: bool
    sin_cuenta_movimientos: int
    proximo_ingreso: ProximoIngresoOut | None = None
    ingresos_mes: float
    gastos_mes: float
    balance_mes: float
    ingresos_mes_anterior: float
    gastos_mes_anterior: float
    gastos_fijos: float
    motivos: list[str]
    top_categorias: list[MotivoOut]


class AdoptarMovimientosOut(BaseModel):
    asignados: int
    cuenta: str
    saldo_actual: float
