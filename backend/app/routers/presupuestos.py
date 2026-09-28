"""CRUD de presupuestos por categoría (aislado por usuario)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..crud_utils import get_owned
from ..deps import get_current_user, get_db
from ..models import Categoria, Presupuesto, Usuario
from ..presupuestos import construir_uno, listar_con_gasto
from ..schemas import PresupuestoIn, PresupuestoOut, PresupuestoUpdate

router = APIRouter(prefix="/presupuestos", tags=["presupuestos"])


@router.get("", response_model=list[PresupuestoOut])
def listar(mes: str | None = None, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    return listar_con_gasto(db, user.id, mes)


@router.post("", response_model=PresupuestoOut, status_code=201)
def crear(data: PresupuestoIn, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    get_owned(db, Categoria, data.categoria_id, user.id)  # valida que sea del usuario
    obj = Presupuesto(usuario_id=user.id, **data.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return construir_uno(db, user.id, obj)


@router.patch("/{id}", response_model=PresupuestoOut)
def actualizar(id: uuid.UUID, data: PresupuestoUpdate, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    obj = get_owned(db, Presupuesto, id, user.id)
    for campo, valor in data.model_dump(exclude_unset=True).items():
        setattr(obj, campo, valor)
    db.commit()
    db.refresh(obj)
    return construir_uno(db, user.id, obj)


@router.delete("/{id}", status_code=204)
def eliminar(id: uuid.UUID, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    obj = get_owned(db, Presupuesto, id, user.id)
    db.delete(obj)
    db.commit()
