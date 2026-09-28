"""CRUD de suscripciones (aislado por usuario)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..crud_utils import get_owned
from ..deps import get_current_user, get_db
from ..models import Categoria, Cuenta, Etiqueta, Suscripcion, Tarjeta, Usuario
from ..schemas import SuscripcionIn, SuscripcionOut, SuscripcionUpdate

router = APIRouter(prefix="/suscripciones", tags=["suscripciones"])


def _validar_refs(db: Session, user: Usuario, campos: dict) -> None:
    """Categoría, tarjeta, etiqueta y cuenta deben existir y ser del usuario."""
    for campo, modelo in (
        ("categoria_id", Categoria),
        ("tarjeta_id", Tarjeta),
        ("etiqueta_id", Etiqueta),
        ("cuenta_id", Cuenta),
    ):
        valor = campos.get(campo)
        if valor is not None:
            get_owned(db, modelo, valor, user.id)


@router.get("", response_model=list[SuscripcionOut])
def listar(db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    return db.scalars(
        select(Suscripcion)
        .where(Suscripcion.usuario_id == user.id)
        .order_by(Suscripcion.proximo_pago.asc().nulls_last(), Suscripcion.nombre)
    ).all()


@router.post("", response_model=SuscripcionOut, status_code=201)
def crear(data: SuscripcionIn, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    _validar_refs(db, user, data.model_dump())
    obj = Suscripcion(usuario_id=user.id, **data.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.get("/{id}", response_model=SuscripcionOut)
def obtener(id: uuid.UUID, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    return get_owned(db, Suscripcion, id, user.id)


@router.patch("/{id}", response_model=SuscripcionOut)
def actualizar(id: uuid.UUID, data: SuscripcionUpdate, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    obj = get_owned(db, Suscripcion, id, user.id)
    campos = data.model_dump(exclude_unset=True)
    _validar_refs(db, user, campos)
    for campo, valor in campos.items():
        setattr(obj, campo, valor)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/{id}", status_code=204)
def eliminar(id: uuid.UUID, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    obj = get_owned(db, Suscripcion, id, user.id)
    db.delete(obj)
    db.commit()
