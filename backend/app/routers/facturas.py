"""Facturas PDF: subir, listar, asociar a transacción y eliminar."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..crud_utils import get_owned
from ..deps import get_current_user, get_db
from ..facturas import detectar_fecha, detectar_monto, extraer_texto
from ..models import Factura, Transaccion, Usuario
from ..schemas import AsociarFacturaIn, FacturaOut

router = APIRouter(prefix="/facturas", tags=["facturas"])


@router.get("", response_model=list[FacturaOut])
def listar(db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    return db.scalars(
        select(Factura).where(Factura.usuario_id == user.id).order_by(Factura.creada_en.desc())
    ).all()


@router.post("", response_model=FacturaOut, status_code=201)
async def subir(
    archivo: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    contenido = await archivo.read()
    if not contenido:
        raise HTTPException(status_code=400, detail="El archivo está vacío")
    if len(contenido) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="El archivo supera 10 MB")

    texto = extraer_texto(contenido)
    factura = Factura(
        usuario_id=user.id,
        nombre_archivo=archivo.filename or "factura.pdf",
        texto_extraido=texto[:20000] if texto else None,
        monto_detectado=detectar_monto(texto) if texto else None,
        fecha_detectada=detectar_fecha(texto) if texto else None,
    )
    db.add(factura)
    db.commit()
    db.refresh(factura)
    return factura


@router.post("/{id}/asociar", response_model=FacturaOut)
def asociar(
    id: uuid.UUID,
    data: AsociarFacturaIn,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    factura = get_owned(db, Factura, id, user.id)
    get_owned(db, Transaccion, data.transaccion_id, user.id)  # valida que sea del usuario
    factura.transaccion_id = data.transaccion_id
    db.commit()
    db.refresh(factura)
    return factura


@router.delete("/{id}", status_code=204)
def eliminar(id: uuid.UUID, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    factura = get_owned(db, Factura, id, user.id)
    db.delete(factura)
    db.commit()
