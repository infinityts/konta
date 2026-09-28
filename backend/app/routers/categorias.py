"""CRUD de categorías (siempre raíces) — aislado por usuario.

El anidamiento ya no vive aquí: el árbol es
**Categoría → Etiqueta → Subetiqueta** (ver `routers/etiquetas.py`).
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..crud_utils import get_owned
from ..deps import get_current_user, get_db
from ..models import Categoria, Usuario
from ..schemas import CategoriaIn, CategoriaOut, CategoriaUpdate

router = APIRouter(prefix="/categorias", tags=["categorias"])


def _msg_duplicado(nombre: str) -> str:
    return f"Ya existe una categoría «{nombre}»."


def _existe(db: Session, user: Usuario, nombre: str, excluir=None) -> bool:
    condiciones = [Categoria.usuario_id == user.id, func.lower(Categoria.nombre) == nombre.lower()]
    if excluir is not None:
        condiciones.append(Categoria.id != excluir)
    return bool(db.scalar(select(func.count()).select_from(Categoria).where(*condiciones)))


@router.get("", response_model=list[CategoriaOut])
def listar(db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    return db.scalars(
        select(Categoria)
        .where(Categoria.usuario_id == user.id)
        .order_by(Categoria.tipo, Categoria.nombre)
    ).all()


@router.get("/arbol")
def arbol(db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    """Las categorías son planas; el anidamiento está en las etiquetas."""
    categorias = db.scalars(
        select(Categoria).where(Categoria.usuario_id == user.id).order_by(Categoria.nombre)
    ).all()
    return [
        {
            "id": c.id,
            "nombre": c.nombre,
            "tipo": c.tipo.value,
            "icono": c.icono,
            "color": c.color,
            "subcategorias": [],
        }
        for c in categorias
    ]


@router.post("", response_model=CategoriaOut, status_code=201)
def crear(data: CategoriaIn, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    nombre = data.nombre.strip()
    if _existe(db, user, nombre):
        raise HTTPException(status_code=400, detail=_msg_duplicado(nombre))
    obj = Categoria(usuario_id=user.id, **{**data.model_dump(), "nombre": nombre})
    db.add(obj)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail=_msg_duplicado(nombre))
    db.refresh(obj)
    return obj


@router.get("/{id}", response_model=CategoriaOut)
def obtener(id: uuid.UUID, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    return get_owned(db, Categoria, id, user.id)


@router.patch("/{id}", response_model=CategoriaOut)
def actualizar(id: uuid.UUID, data: CategoriaUpdate, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    obj = get_owned(db, Categoria, id, user.id)
    campos = data.model_dump(exclude_unset=True)
    if "nombre" in campos:
        campos["nombre"] = (campos["nombre"] or "").strip()
    nombre = campos.get("nombre", obj.nombre)
    if _existe(db, user, nombre, excluir=id):
        raise HTTPException(status_code=400, detail=_msg_duplicado(nombre))
    for campo, valor in campos.items():
        setattr(obj, campo, valor)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail=_msg_duplicado(nombre))
    db.refresh(obj)
    return obj


@router.delete("/{id}", status_code=204)
def eliminar(id: uuid.UUID, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    obj = get_owned(db, Categoria, id, user.id)
    db.delete(obj)  # sus etiquetas se eliminan en cascada
    db.commit()
