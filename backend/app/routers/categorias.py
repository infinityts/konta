"""CRUD de categorías y subcategorías (aislado por usuario)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..crud_utils import get_owned
from ..deps import get_current_user, get_db
from ..models import Categoria, Usuario
from ..schemas import CategoriaIn, CategoriaOut, CategoriaUpdate

router = APIRouter(prefix="/categorias", tags=["categorias"])


def _validar_padre(db: Session, user: Usuario, padre_id, propia_id=None) -> None:
    """El padre debe ser del usuario y no puede generar un ciclo."""
    if padre_id is None:
        return
    if propia_id is not None and padre_id == propia_id:
        raise HTTPException(status_code=400, detail="Una categoría no puede ser su propia categoría padre")
    padre = get_owned(db, Categoria, padre_id, user.id)
    if propia_id is not None and padre.padre_id == propia_id:
        raise HTTPException(status_code=400, detail="Eso crearía un ciclo entre categorías")


@router.get("", response_model=list[CategoriaOut])
def listar(db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    return db.scalars(
        select(Categoria).where(Categoria.usuario_id == user.id).order_by(Categoria.nombre)
    ).all()


@router.get("/arbol")
def arbol(db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    """Categorías como árbol: raíces con sus subcategorías."""
    categorias = db.scalars(
        select(Categoria).where(Categoria.usuario_id == user.id).order_by(Categoria.nombre)
    ).all()
    ids = {c.id for c in categorias}
    hijos: dict = {}
    for c in categorias:
        hijos.setdefault(c.padre_id if c.padre_id in ids else None, []).append(c)

    def nodo(c: Categoria) -> dict:
        return {
            "id": c.id,
            "nombre": c.nombre,
            "tipo": c.tipo.value,
            "icono": c.icono,
            "color": c.color,
            "subcategorias": [
                {"id": s.id, "nombre": s.nombre, "tipo": s.tipo.value}
                for s in hijos.get(c.id, [])
            ],
        }

    return [nodo(c) for c in hijos.get(None, [])]


@router.post("", response_model=CategoriaOut, status_code=201)
def crear(data: CategoriaIn, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    _validar_padre(db, user, data.padre_id)
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
    campos = data.model_dump(exclude_unset=True)
    if "padre_id" in campos:
        _validar_padre(db, user, campos["padre_id"], propia_id=id)
    for campo, valor in campos.items():
        setattr(obj, campo, valor)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/{id}", status_code=204)
def eliminar(id: uuid.UUID, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    obj = get_owned(db, Categoria, id, user.id)
    db.delete(obj)
    db.commit()
