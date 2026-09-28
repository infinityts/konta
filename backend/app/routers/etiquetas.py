"""CRUD de etiquetas y subetiquetas dentro de categorías (aislado por usuario).

Jerarquía: **Categoría → Etiqueta → Subetiqueta**.

Los nombres son **únicos entre hermanos** (mismo padre) y **no distinguen
mayúsculas**. En categorías distintas el mismo nombre sí se puede repetir.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..crud_utils import get_owned
from ..defaults import sembrar_etiquetas_diccionario
from ..deps import get_current_user, get_db
from ..models import Categoria, Etiqueta, Usuario
from ..schemas import (
    DiccionarioEtiquetasOut,
    EtiquetaIn,
    EtiquetaOut,
    EtiquetaUpdate,
)

router = APIRouter(prefix="/etiquetas", tags=["etiquetas"])


def _msg(nombre: str, padre_id) -> str:
    if padre_id is None:
        return f"Ya existe una etiqueta «{nombre}» en esa categoría."
    return f"Ya existe una subetiqueta «{nombre}» dentro de esa etiqueta."


def _existe_hermana(db: Session, user: Usuario, nombre: str, categoria_id, padre_id, excluir=None) -> bool:
    condiciones = [Etiqueta.usuario_id == user.id, func.lower(Etiqueta.nombre) == nombre.lower()]
    if padre_id is None:
        condiciones.append(Etiqueta.padre_id.is_(None))
        condiciones.append(
            Etiqueta.categoria_id.is_(None) if categoria_id is None else Etiqueta.categoria_id == categoria_id
        )
    else:
        condiciones.append(Etiqueta.padre_id == padre_id)
    if excluir is not None:
        condiciones.append(Etiqueta.id != excluir)
    return bool(db.scalar(select(func.count()).select_from(Etiqueta).where(*condiciones)))


def _validar(db: Session, user: Usuario, nombre: str, categoria_id, padre_id, propia_id=None):
    """Limpia el nombre y resuelve padre/categoría. Devuelve (nombre, categoria_id)."""
    nombre = (nombre or "").strip()
    if not nombre:
        raise HTTPException(status_code=400, detail="El nombre no puede estar vacío")

    if padre_id is not None:
        if propia_id is not None and padre_id == propia_id:
            raise HTTPException(status_code=400, detail="Una etiqueta no puede ser su propio padre")
        padre = get_owned(db, Etiqueta, padre_id, user.id)
        # Una subetiqueta vive en la misma categoría que su etiqueta
        categoria_id = padre.categoria_id
    elif categoria_id is not None:
        get_owned(db, Categoria, categoria_id, user.id)

    return nombre, categoria_id


@router.post("/diccionario", response_model=DiccionarioEtiquetasOut, status_code=201)
def crear_diccionario(
    db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)
):
    """Crea las etiquetas que el diccionario del OCR sabe reconocer y le falten.

    Pensado para quien ya tenía cuenta antes de que se sembraran: sin estas
    etiquetas el clasificador no tiene con qué comparar (empareja contra nombres
    de etiquetas) y toda tira de mercado sale «sin clasificar». Idempotente.
    """
    creadas = sembrar_etiquetas_diccionario(db, user.id)
    db.commit()
    for etiqueta in creadas:
        db.refresh(etiqueta)
    return DiccionarioEtiquetasOut(
        total_creadas=len(creadas),
        creadas=[EtiquetaOut.model_validate(e) for e in creadas],
    )


@router.get("", response_model=list[EtiquetaOut])
def listar(db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    return db.scalars(
        select(Etiqueta)
        .where(Etiqueta.usuario_id == user.id)
        .order_by(Etiqueta.categoria_id, Etiqueta.padre_id, Etiqueta.nombre)
    ).all()


@router.post("", response_model=EtiquetaOut, status_code=201)
def crear(data: EtiquetaIn, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    nombre, categoria_id = _validar(db, user, data.nombre, data.categoria_id, data.padre_id)
    if _existe_hermana(db, user, nombre, categoria_id, data.padre_id):
        raise HTTPException(status_code=400, detail=_msg(nombre, data.padre_id))

    obj = Etiqueta(
        usuario_id=user.id,
        nombre=nombre,
        color=data.color,
        categoria_id=categoria_id,
        padre_id=data.padre_id,
    )
    db.add(obj)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail=_msg(nombre, data.padre_id)) from None
    db.refresh(obj)
    return obj


@router.get("/{id}", response_model=EtiquetaOut)
def obtener(id: uuid.UUID, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    return get_owned(db, Etiqueta, id, user.id)


@router.patch("/{id}", response_model=EtiquetaOut)
def actualizar(id: uuid.UUID, data: EtiquetaUpdate, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    obj = get_owned(db, Etiqueta, id, user.id)
    cambios = data.model_dump(exclude_unset=True)

    nombre, categoria_id = _validar(
        db,
        user,
        cambios.get("nombre", obj.nombre),
        cambios.get("categoria_id", obj.categoria_id),
        cambios.get("padre_id", obj.padre_id),
        propia_id=id,
    )
    padre_id = cambios.get("padre_id", obj.padre_id)
    if _existe_hermana(db, user, nombre, categoria_id, padre_id, excluir=id):
        raise HTTPException(status_code=400, detail=_msg(nombre, padre_id))

    obj.nombre = nombre
    if "color" in cambios:
        obj.color = cambios["color"]
    if "padre_id" in cambios:
        obj.padre_id = padre_id
    cambio_categoria = obj.categoria_id != categoria_id
    obj.categoria_id = categoria_id

    if cambio_categoria:
        # Las subetiquetas acompañan a su etiqueta
        db.execute(update(Etiqueta).where(Etiqueta.padre_id == id).values(categoria_id=categoria_id))

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail=_msg(nombre, padre_id)) from None
    db.refresh(obj)
    return obj


@router.delete("/{id}", status_code=204)
def eliminar(id: uuid.UUID, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    obj = get_owned(db, Etiqueta, id, user.id)
    db.delete(obj)  # las subetiquetas se eliminan en cascada
    db.commit()
