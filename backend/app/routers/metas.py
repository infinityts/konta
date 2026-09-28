"""CRUD de metas de ahorro y sus aportes."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..crud_utils import get_owned
from ..deps import get_current_user, get_db
from ..metas import construir_una, listar
from ..models import AporteMeta, MetaAhorro, Usuario
from ..recurrencia import hoy
from ..schemas import AporteIn, AporteOut, MetaIn, MetaOut, MetaUpdate

router = APIRouter(prefix="/metas", tags=["metas"])


@router.get("", response_model=list[MetaOut])
def listar_metas(db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    return listar(db, user.id)


@router.post("", response_model=MetaOut, status_code=201)
def crear(data: MetaIn, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    obj = MetaAhorro(usuario_id=user.id, **data.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return construir_una(db, obj)


@router.patch("/{id}", response_model=MetaOut)
def actualizar(id: uuid.UUID, data: MetaUpdate, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    obj = get_owned(db, MetaAhorro, id, user.id)
    for campo, valor in data.model_dump(exclude_unset=True).items():
        setattr(obj, campo, valor)
    db.commit()
    db.refresh(obj)
    return construir_una(db, obj)


@router.delete("/{id}", status_code=204)
def eliminar(id: uuid.UUID, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    obj = get_owned(db, MetaAhorro, id, user.id)
    db.delete(obj)
    db.commit()


@router.get("/{id}/aportes", response_model=list[AporteOut])
def listar_aportes(id: uuid.UUID, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    get_owned(db, MetaAhorro, id, user.id)
    return db.scalars(
        select(AporteMeta)
        .where(AporteMeta.meta_id == id, AporteMeta.usuario_id == user.id)
        .order_by(AporteMeta.fecha.desc())
    ).all()


@router.post("/{id}/aportes", response_model=MetaOut, status_code=201)
def agregar_aporte(id: uuid.UUID, data: AporteIn, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    meta = get_owned(db, MetaAhorro, id, user.id)
    db.add(
        AporteMeta(
            usuario_id=user.id,
            meta_id=meta.id,
            monto=data.monto,
            fecha=data.fecha or hoy(),
            notas=data.notas,
        )
    )
    db.commit()
    db.refresh(meta)
    return construir_una(db, meta)


@router.delete("/aportes/{aporte_id}", status_code=204)
def eliminar_aporte(aporte_id: uuid.UUID, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    obj = get_owned(db, AporteMeta, aporte_id, user.id)
    db.delete(obj)
    db.commit()
