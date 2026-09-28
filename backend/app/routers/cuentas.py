"""Cuentas de dinero con saldo inicial y saldo actual."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..crud_utils import get_owned
from ..deps import get_current_user, get_db
from ..models import Cuenta, Usuario
from ..saldos import saldo_cuentas, saldo_de_cuenta
from ..schemas import CuentaIn, CuentaOut, CuentaUpdate, SaldoResumenOut

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
