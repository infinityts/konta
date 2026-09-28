"""Productos y precios de mercado (con comparativo por tienda)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..crud_utils import get_owned
from ..deps import get_current_user, get_db
from ..mercado import comparativo
from ..models import PrecioMercado, Producto, Usuario
from ..recurrencia import hoy
from ..schemas import (
    ComparativoOut,
    PrecioIn,
    PrecioOut,
    ProductoIn,
    ProductoOut,
    ProductoUpdate,
)

router = APIRouter(prefix="/productos", tags=["mercado"])


@router.get("", response_model=list[ProductoOut])
def listar(db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    return db.scalars(
        select(Producto).where(Producto.usuario_id == user.id).order_by(Producto.nombre)
    ).all()


@router.post("", response_model=ProductoOut, status_code=201)
def crear(data: ProductoIn, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    obj = Producto(usuario_id=user.id, **data.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.get("/{id}", response_model=ProductoOut)
def obtener(id: uuid.UUID, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    return get_owned(db, Producto, id, user.id)


@router.patch("/{id}", response_model=ProductoOut)
def actualizar(id: uuid.UUID, data: ProductoUpdate, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    obj = get_owned(db, Producto, id, user.id)
    for campo, valor in data.model_dump(exclude_unset=True).items():
        setattr(obj, campo, valor)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/{id}", status_code=204)
def eliminar(id: uuid.UUID, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    obj = get_owned(db, Producto, id, user.id)
    db.delete(obj)
    db.commit()


@router.get("/{id}/comparativo", response_model=ComparativoOut)
def comparativo_producto(id: uuid.UUID, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    producto = get_owned(db, Producto, id, user.id)
    return comparativo(db, user.id, producto)


@router.get("/{id}/precios", response_model=list[PrecioOut])
def listar_precios(id: uuid.UUID, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    get_owned(db, Producto, id, user.id)
    return db.scalars(
        select(PrecioMercado)
        .where(PrecioMercado.producto_id == id, PrecioMercado.usuario_id == user.id)
        .order_by(PrecioMercado.fecha.desc())
    ).all()


@router.post("/{id}/precios", response_model=PrecioOut, status_code=201)
def registrar_precio(id: uuid.UUID, data: PrecioIn, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    producto = get_owned(db, Producto, id, user.id)
    obj = PrecioMercado(
        usuario_id=user.id,
        producto_id=producto.id,
        tienda=data.tienda,
        precio=data.precio,
        moneda=data.moneda,
        fecha=data.fecha or hoy(),
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj
