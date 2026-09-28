"""CRUD de transacciones (aislado por usuario)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..crud_utils import get_owned
from ..deps import get_current_user, get_db
from ..models import Transaccion, Usuario
from ..schemas import TransaccionIn, TransaccionOut, TransaccionUpdate

router = APIRouter(prefix="/transacciones", tags=["transacciones"])


@router.get("", response_model=list[TransaccionOut])
def listar(db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    return db.scalars(
        select(Transaccion)
        .where(Transaccion.usuario_id == user.id)
        .order_by(Transaccion.fecha.desc())
    ).all()


@router.post("", response_model=TransaccionOut, status_code=201)
def crear(data: TransaccionIn, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    obj = Transaccion(usuario_id=user.id, **data.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.get("/{id}", response_model=TransaccionOut)
def obtener(id: uuid.UUID, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    return get_owned(db, Transaccion, id, user.id)


@router.patch("/{id}", response_model=TransaccionOut)
def actualizar(id: uuid.UUID, data: TransaccionUpdate, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    obj = get_owned(db, Transaccion, id, user.id)
    for campo, valor in data.model_dump(exclude_unset=True).items():
        setattr(obj, campo, valor)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/{id}", status_code=204)
def eliminar(id: uuid.UUID, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    obj = get_owned(db, Transaccion, id, user.id)
    db.delete(obj)
    db.commit()
