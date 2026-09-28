"""CRUD de tarjetas (aislado por usuario)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..crud_utils import get_owned
from ..deps import get_current_user, get_db
from ..models import Tarjeta, Usuario
from ..schemas import TarjetaIn, TarjetaOut, TarjetaUpdate

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
