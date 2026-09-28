"""Lista de mercado (items a comprar)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..crud_utils import get_owned
from ..deps import get_current_user, get_db
from ..models import ItemLista, Usuario
from ..schemas import ItemListaIn, ItemListaOut, ItemListaUpdate, ListaMercadoOut

router = APIRouter(prefix="/lista-mercado", tags=["mercado"])


@router.get("", response_model=ListaMercadoOut)
def listar(db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    items = list(
        db.scalars(
            select(ItemLista)
            .where(ItemLista.usuario_id == user.id)
            .order_by(ItemLista.comprado, ItemLista.creada_en)
        ).all()
    )
    total = sum(
        float(i.cantidad) * float(i.precio_estimado)
        for i in items
        if i.precio_estimado is not None
    )
    return {
        "items": items,
        "total_estimado": round(total, 2),
        "pendientes": sum(1 for i in items if not i.comprado),
    }


@router.post("", response_model=ItemListaOut, status_code=201)
def crear(data: ItemListaIn, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    obj = ItemLista(usuario_id=user.id, **data.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.patch("/{id}", response_model=ItemListaOut)
def actualizar(id: uuid.UUID, data: ItemListaUpdate, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    obj = get_owned(db, ItemLista, id, user.id)
    for campo, valor in data.model_dump(exclude_unset=True).items():
        setattr(obj, campo, valor)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/{id}", status_code=204)
def eliminar(id: uuid.UUID, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    obj = get_owned(db, ItemLista, id, user.id)
    db.delete(obj)
    db.commit()
