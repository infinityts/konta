"""Monedas, tasas de cambio y conversión."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..deps import get_current_user, get_db
from ..models import Moneda, TasaCambio, Usuario
from ..recurrencia import hoy
from ..schemas import ConversionOut, MonedaOut, TasaIn, TasaOut
from ..tasas import actualizar_desde_internet, convertir, obtener_tasa

router = APIRouter(tags=["monedas"])


@router.get("/monedas", response_model=list[MonedaOut])
def listar_monedas(db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    return db.scalars(select(Moneda).order_by(Moneda.codigo)).all()


@router.get("/tasas", response_model=list[TasaOut])
def listar_tasas(
    base: str | None = None,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    stmt = select(TasaCambio).order_by(TasaCambio.fecha.desc(), TasaCambio.moneda_origen, TasaCambio.moneda_destino)
    if base:
        stmt = stmt.where(TasaCambio.moneda_origen == base)
    return db.scalars(stmt.limit(200)).all()


@router.post("/tasas", response_model=TasaOut, status_code=201)
def crear_tasa(data: TasaIn, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    for codigo in (data.moneda_origen, data.moneda_destino):
        if db.get(Moneda, codigo) is None:
            raise HTTPException(status_code=400, detail=f"Moneda desconocida: {codigo}")
    if data.moneda_origen == data.moneda_destino:
        raise HTTPException(status_code=400, detail="Las monedas deben ser distintas")
    obj = TasaCambio(
        moneda_origen=data.moneda_origen,
        moneda_destino=data.moneda_destino,
        fecha=data.fecha or hoy(),
        tasa=data.tasa,
        fuente=data.fuente or "manual",
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/tasas/{id}", status_code=204)
def eliminar_tasa(id: uuid.UUID, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    obj = db.get(TasaCambio, id)
    if obj is None:
        raise HTTPException(status_code=404, detail="Tasa no encontrada")
    db.delete(obj)
    db.commit()


@router.post("/tasas/actualizar")
def actualizar_tasas(base: str = "USD", db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    """Descarga las tasas actuales desde internet (open.er-api.com)."""
    try:
        n = actualizar_desde_internet(db, base.upper())
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    return {"actualizadas": n, "base": base.upper(), "fuente": "open.er-api.com"}


@router.get("/convertir", response_model=ConversionOut)
def convertir_endpoint(
    de: str,
    a: str,
    monto: float,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    de, a = de.upper(), a.upper()
    tasa = obtener_tasa(db, de, a)
    if tasa is None:
        raise HTTPException(
            status_code=404,
            detail=f"No hay tasa registrada de {de} a {a}. Regístrala o actualiza desde internet.",
        )
    from decimal import Decimal

    resultado = convertir(db, de, a, Decimal(str(monto)))
    return {"de": de, "a": a, "monto": Decimal(str(monto)), "tasa": tasa, "resultado": resultado}
