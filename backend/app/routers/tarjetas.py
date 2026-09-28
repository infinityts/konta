"""Tarjetas: deuda por moneda (del extracto) y simulador de intereses."""

from __future__ import annotations

import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..crud_utils import get_owned
from ..deps import get_current_user, get_db
from ..intereses import pago_minimo, simular_pago
from ..models import DeudaTarjeta, Tarjeta, Usuario
from ..recurrencia import hoy
from ..schemas import (
    DeudaIn,
    DeudaOut,
    SimulacionOut,
    TarjetaConDeudaOut,
    TarjetaIn,
    TarjetaOut,
    TarjetaUpdate,
)
from ..tasas import obtener_tasa

router = APIRouter(prefix="/tarjetas", tags=["tarjetas"])


def _con_deuda(db: Session, tarjeta: Tarjeta) -> dict:
    """Tarjeta + deuda por moneda + total en COP (si hay tasas para convertir)."""
    deudas = db.scalars(
        select(DeudaTarjeta)
        .where(DeudaTarjeta.tarjeta_id == tarjeta.id, DeudaTarjeta.usuario_id == tarjeta.usuario_id)
        .order_by(DeudaTarjeta.fecha.desc())
    ).all()

    por_moneda: dict[str, float] = {}
    for d in deudas:
        por_moneda[d.moneda] = por_moneda.get(d.moneda, 0.0) + float(d.monto)

    total_cop = 0.0
    completo = True
    for moneda, monto in por_moneda.items():
        if moneda == "COP":
            total_cop += monto
            continue
        tasa = obtener_tasa(db, moneda, "COP")
        if tasa is None:
            completo = False
            break
        total_cop += monto * float(tasa)

    return {
        "id": tarjeta.id,
        "usuario_id": tarjeta.usuario_id,
        "nombre": tarjeta.nombre,
        "banco": tarjeta.banco,
        "tipo": tarjeta.tipo,
        "moneda": tarjeta.moneda,
        "dia_corte": tarjeta.dia_corte,
        "dia_pago": tarjeta.dia_pago,
        "limite": tarjeta.limite,
        "tasa_interes": tarjeta.tasa_interes,
        "activa": tarjeta.activa,
        "deudas": deudas,
        "deuda_por_moneda": por_moneda,
        "deuda_total_cop": round(total_cop, 2) if completo else None,
    }


@router.get("", response_model=list[TarjetaConDeudaOut])
def listar(db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    tarjetas = db.scalars(
        select(Tarjeta).where(Tarjeta.usuario_id == user.id).order_by(Tarjeta.nombre)
    ).all()
    return [_con_deuda(db, t) for t in tarjetas]


@router.post("", response_model=TarjetaOut, status_code=201)
def crear(data: TarjetaIn, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    obj = Tarjeta(usuario_id=user.id, **data.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.get("/{id}", response_model=TarjetaConDeudaOut)
def obtener(id: uuid.UUID, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    return _con_deuda(db, get_owned(db, Tarjeta, id, user.id))


@router.patch("/{id}", response_model=TarjetaOut)
def actualizar(id: uuid.UUID, data: TarjetaUpdate, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    obj = get_owned(db, Tarjeta, id, user.id)
    for campo, valor in data.model_dump(exclude_unset=True).items():
        setattr(obj, campo, valor)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/{id}", status_code=204)
def eliminar(id: uuid.UUID, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    obj = get_owned(db, Tarjeta, id, user.id)
    db.delete(obj)
    db.commit()


# --- deuda de la tarjeta (lo que dice el extracto) ---


@router.get("/{id}/deudas", response_model=list[DeudaOut])
def listar_deudas(id: uuid.UUID, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    get_owned(db, Tarjeta, id, user.id)
    return db.scalars(
        select(DeudaTarjeta)
        .where(DeudaTarjeta.tarjeta_id == id, DeudaTarjeta.usuario_id == user.id)
        .order_by(DeudaTarjeta.fecha.desc())
    ).all()


@router.post("/{id}/deudas", response_model=DeudaOut, status_code=201)
def registrar_deuda(id: uuid.UUID, data: DeudaIn, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    tarjeta = get_owned(db, Tarjeta, id, user.id)
    obj = DeudaTarjeta(
        usuario_id=user.id,
        tarjeta_id=tarjeta.id,
        moneda=data.moneda,
        monto=data.monto,
        fecha=data.fecha or hoy(),
        notas=data.notas,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/{id}/deudas/{deuda_id}", status_code=204)
def eliminar_deuda(id: uuid.UUID, deuda_id: uuid.UUID, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    get_owned(db, Tarjeta, id, user.id)
    obj = get_owned(db, DeudaTarjeta, deuda_id, user.id)
    db.delete(obj)
    db.commit()


@router.get("/{id}/simulador", response_model=SimulacionOut)
def simular(
    id: uuid.UUID,
    saldo: float | None = None,
    pago_mensual: float | None = None,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """Simula el pago de la deuda. Si no se indica saldo, usa la deuda registrada.

    Si no se indica `pago_mensual`, se usa el 5% del saldo como pago mínimo.
    """
    tarjeta = get_owned(db, Tarjeta, id, user.id)
    if tarjeta.tasa_interes is None:
        raise HTTPException(status_code=400, detail="La tarjeta no tiene tasa de interés configurada")

    if saldo is None:
        saldo = _con_deuda(db, tarjeta)["deuda_total_cop"]
        if saldo is None:
            raise HTTPException(
                status_code=400,
                detail="No hay deuda registrada (o falta la tasa de cambio). Registra la deuda o indica el saldo.",
            )

    saldo_d = Decimal(str(saldo))
    if saldo_d <= 0:
        raise HTTPException(status_code=400, detail="El saldo debe ser mayor que cero")
    pago_d = Decimal(str(pago_mensual)) if pago_mensual else pago_minimo(saldo_d)

    return simular_pago(saldo_d, tarjeta.tasa_interes, pago_d)
