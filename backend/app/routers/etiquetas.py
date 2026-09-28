"""CRUD de etiquetas y subetiquetas (aislado por usuario).

Modelo autojerárquico: `padre_id` NULL = etiqueta raíz; con valor = subetiqueta.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..crud_utils import get_owned
from ..deps import get_current_user, get_db
from ..models import Etiqueta, Usuario
from ..schemas import EtiquetaIn, EtiquetaOut, EtiquetaUpdate

router = APIRouter(prefix="/etiquetas", tags=["etiquetas"])


@router.get("", response_model=list[EtiquetaOut])
def listar(db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    return db.scalars(
        select(Etiqueta).where(Etiqueta.usuario_id == user.id).order_by(Etiqueta.nombre)
    ).all()


@router.post("", response_model=EtiquetaOut, status_code=201)
def crear(data: EtiquetaIn, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    if data.padre_id is not None:
        get_owned(db, Etiqueta, data.padre_id, user.id)  # valida que exista y sea del usuario
    obj = Etiqueta(usuario_id=user.id, **data.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.get("/{id}", response_model=EtiquetaOut)
def obtener(id: uuid.UUID, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    return get_owned(db, Etiqueta, id, user.id)


@router.patch("/{id}", response_model=EtiquetaOut)
def actualizar(id: uuid.UUID, data: EtiquetaUpdate, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    obj = get_owned(db, Etiqueta, id, user.id)
    cambios = data.model_dump(exclude_unset=True)
    if cambios.get("padre_id") is not None:
        if cambios["padre_id"] == id:
            raise HTTPException(status_code=400, detail="Una etiqueta no puede ser su propio padre")
        get_owned(db, Etiqueta, cambios["padre_id"], user.id)
    for campo, valor in cambios.items():
        setattr(obj, campo, valor)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/{id}", status_code=204)
def eliminar(id: uuid.UUID, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    obj = get_owned(db, Etiqueta, id, user.id)
    db.delete(obj)  # las subetiquetas se eliminan en cascada
    db.commit()
