"""CRUD de tarjetas (aislado por usuario)."""

from __future__ import annotations

import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..crud_utils import get_owned
from ..deps import get_current_user, get_db
from ..intereses import pago_minimo, simular_pago
from ..models import Tarjeta, Usuario
from ..schemas import SimulacionOut, TarjetaIn, TarjetaOut, TarjetaUpdate

router = APIRouter(prefix="/tarjetas", tags=["tarjetas"])


@router.get("", response_model=list[TarjetaOut])
def listar(db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    return db.scalars(
        select(Tarjeta).where(Tarjeta.usuario_id == user.id).order_by(Tarjeta.nombre)
    ).all()


@router.post("", response_model=TarjetaOut, status_code=201)
def crear(data: TarjetaIn, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    obj = Tarjeta(usuario_id=user.id, **data.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.get("/{id}", response_model=TarjetaOut)
def obtener(id: uuid.UUID, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    return get_owned(db, Tarjeta, id, user.id)


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


@router.get("/{id}/simulador", response_model=SimulacionOut)
def simular(
    id: uuid.UUID,
    saldo: float,
    pago_mensual: float | None = None,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """Simula el pago de la deuda de una tarjeta con su tasa mensual.

    Si no se indica `pago_mensual`, se usa el 5% del saldo como pago mínimo.
    """
    tarjeta = get_owned(db, Tarjeta, id, user.id)
    if tarjeta.tasa_interes is None:
        raise HTTPException(status_code=400, detail="La tarjeta no tiene tasa de interés configurada")

    saldo_d = Decimal(str(saldo))
    if saldo_d <= 0:
        raise HTTPException(status_code=400, detail="El saldo debe ser mayor que cero")
    pago_d = Decimal(str(pago_mensual)) if pago_mensual else pago_minimo(saldo_d)

    return simular_pago(saldo_d, tarjeta.tasa_interes, pago_d)
