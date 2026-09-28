"""Cuentas de dinero con saldo inicial y saldo actual."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import update
from sqlalchemy.orm import Session

from ..crud_utils import get_owned
from ..deps import get_current_user, get_db
from ..models import Cuenta, Transaccion, Usuario
from ..saldos import saldo_cuentas, saldo_de_cuenta
from ..schemas import (
    AdoptarMovimientosOut,
    CuentaIn,
    CuentaOut,
    CuentaUpdate,
    SaldoResumenOut,
)

router = APIRouter(prefix="/cuentas", tags=["cuentas"])


@router.get("", response_model=SaldoResumenOut)
def listar(db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    return saldo_cuentas(db, user.id)


@router.post("", response_model=CuentaOut, status_code=201)
def crear(data: CuentaIn, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    obj = Cuenta(usuario_id=user.id, **data.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return saldo_de_cuenta(db, obj)


@router.patch("/{id}", response_model=CuentaOut)
def actualizar(id: uuid.UUID, data: CuentaUpdate, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    obj = get_owned(db, Cuenta, id, user.id)
    for campo, valor in data.model_dump(exclude_unset=True).items():
        setattr(obj, campo, valor)
    db.commit()
    db.refresh(obj)
    return saldo_de_cuenta(db, obj)


@router.delete("/{id}", status_code=204)
def eliminar(id: uuid.UUID, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    obj = get_owned(db, Cuenta, id, user.id)
    db.delete(obj)
    db.commit()


@router.post("/{id}/adoptar-movimientos", response_model=AdoptarMovimientosOut)
def adoptar_movimientos(id: uuid.UUID, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    """Asigna a esta cuenta todos los movimientos que están sin cuenta.

    Útil para poner al día el saldo cuando ya tenías transacciones registradas.
    """
    cuenta = get_owned(db, Cuenta, id, user.id)
    resultado = db.execute(
        update(Transaccion)
        .where(Transaccion.usuario_id == user.id, Transaccion.cuenta_id.is_(None))
        .values(cuenta_id=cuenta.id)
    )
    db.commit()
    db.refresh(cuenta)
    detalle = saldo_de_cuenta(db, cuenta)
    return {"asignados": resultado.rowcount or 0, "cuenta": cuenta.nombre, "saldo_actual": detalle["saldo_actual"]}
