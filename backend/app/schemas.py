"""Esquemas Pydantic (entradas/salidas de la API)."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from .models import EstadoSuscripcion, Periodicidad, TipoCategoria, TipoTarjeta, TipoTransaccion


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
    notas: str | None = None


class TransaccionOut(TransaccionIn):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    usuario_id: uuid.UUID
