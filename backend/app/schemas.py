"""Esquemas Pydantic (entradas/salidas de la API)."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

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
    activa: bool | None = None


class TarjetaOut(TarjetaIn):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    usuario_id: uuid.UUID


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
    # NULL = etiqueta raíz; con valor = subetiqueta de esa etiqueta
    padre_id: uuid.UUID | None = None


class EtiquetaUpdate(BaseModel):
    nombre: str | None = None
    color: str | None = None
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
    tipo: str
    total: float
