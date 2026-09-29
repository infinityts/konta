"""Esquemas de los extractos bancarios."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class MovimientoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    orden: int
    fecha: date | None
    descripcion: str
    valor: Decimal
    moneda: str
    saldo: Decimal | None
    monto_original: Decimal | None
    moneda_original: str | None
    tasa_cambio: Decimal | None
    cuotas_n: int | None
    cuotas_total: int | None
    cuota_mes: Decimal | None
    valor_pendiente: Decimal | None
    titular: str | None
    tipo: str
    categoria_id: uuid.UUID | None
    etiqueta_id: uuid.UUID | None
    origen: str
    # Informativo = no es un gasto nuevo (capital de compras de meses anteriores)
    es_informativo: bool


class ExtractoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tipo: str
    formato: str
    banco: str | None
    nombre_archivo: str
    moneda: str
    cuenta_id: uuid.UUID | None
    tarjeta_id: uuid.UUID | None
    periodo_desde: date | None
    periodo_hasta: date | None
    fecha_corte: date | None
    fecha_pago: date | None
    compras: Decimal | None
    abonos: Decimal | None
    intereses: Decimal | None
    otros_cargos: Decimal | None
    pago_total: Decimal | None
    pago_minimo: Decimal | None
    cupo_total: Decimal | None
    cupo_disponible: Decimal | None
    conciliacion_ok: bool
    creado_en: datetime


class ExtractoDetalleOut(ExtractoOut):
    saldo_anterior: Decimal | None = None
    intereses_mora: Decimal | None = None
    movimientos: list[MovimientoOut] = []
    # Controles de la conciliación: qué se comparó, qué se calculó y qué dice el banco
    conciliacion: list[dict] = []


class TramoOut(BaseModel):
    categoria: str
    total: Decimal
    etiquetas: list[str]


class AnalisisOut(BaseModel):
    extracto_id: uuid.UUID
    # Moneda en la que están expresados los totales (la del extracto) y cuál se pidió
    moneda: str
    moneda_extracto: str
    moneda_solicitada: str
    conversion_aplicada: bool
    conciliacion_ok: bool
    conciliacion: list[dict]

    compras: Decimal
    pagos: Decimal
    intereses: Decimal
    comisiones: Decimal
    costos_financieros: Decimal
    movimientos: int
    movimientos_informativos: int

    por_moneda: dict[str, dict[str, Decimal | int]]
    por_categoria: list[TramoOut]
    compromiso_futuro: dict[str, Decimal]

    cupo_total: Decimal | None
    cupo_disponible: Decimal | None
    cupo_utilizado: Decimal | None
    pago_total: Decimal | None
    pago_minimo: Decimal | None
    intereses_declarados: Decimal | None

    avisos: list[str]
    # Compras en divisa sin tasa de cambio en el extracto: no se convierte, se avisa
    sin_tasa: list[dict]
