"""CRUD de categorías (aislado por usuario)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..crud_utils import get_owned
from ..deps import get_current_user, get_db
from ..models import Categoria, Usuario
from ..schemas import CategoriaIn, CategoriaOut, CategoriaUpdate

router = APIRouter(prefix="/categorias", tags=["categorias"])


@router.get("", response_model=list[CategoriaOut])
def listar(db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    return db.scalars(
        select(Categoria).where(Categoria.usuario_id == user.id).order_by(Categoria.nombre)
    ).all()


@router.post("", response_model=CategoriaOut, status_code=201)
def crear(data: CategoriaIn, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    obj = Categoria(usuario_id=user.id, **data.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.get("/{id}", response_model=CategoriaOut)
def obtener(id: uuid.UUID, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    return get_owned(db, Categoria, id, user.id)


@router.patch("/{id}", response_model=CategoriaOut)
def actualizar(id: uuid.UUID, data: CategoriaUpdate, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    obj = get_owned(db, Categoria, id, user.id)
    for campo, valor in data.model_dump(exclude_unset=True).items():
        setattr(obj, campo, valor)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/{id}", status_code=204)
def eliminar(id: uuid.UUID, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    obj = get_owned(db, Categoria, id, user.id)
    db.delete(obj)
    db.commit()
