"""Tasas de cambio: consulta, conversión y actualización desde internet.

Usa la API pública gratuita https://open.er-api.com (sin clave).
"""

from __future__ import annotations

import json
import urllib.request
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Moneda, TasaCambio
from .recurrencia import hoy

FUENTE = "open.er-api.com"


def obtener_tasa(db: Session, de: str, a: str) -> Decimal | None:
    """Tasa de `de` a `a` (la más reciente). Prueba la inversa si no existe directa."""
    if de == a:
        return Decimal("1")
    directa = db.scalar(
        select(TasaCambio)
        .where(TasaCambio.moneda_origen == de, TasaCambio.moneda_destino == a)
        .order_by(TasaCambio.fecha.desc())
        .limit(1)
    )
    if directa is not None:
        return directa.tasa
    inversa = db.scalar(
        select(TasaCambio)
        .where(TasaCambio.moneda_origen == a, TasaCambio.moneda_destino == de)
        .order_by(TasaCambio.fecha.desc())
        .limit(1)
    )
    if inversa is not None and inversa.tasa:
        return Decimal("1") / inversa.tasa
    return None


def convertir(db: Session, de: str, a: str, monto: Decimal) -> Decimal | None:
    tasa = obtener_tasa(db, de, a)
    if tasa is None:
        return None
    return (monto * tasa).quantize(Decimal("0.01"))


def actualizar_desde_internet(db: Session, base: str = "USD") -> int:
    """Descarga las tasas de la API pública y las guarda (una por moneda del catálogo)."""
    url = f"https://open.er-api.com/v6/latest/{base}"
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:  # noqa: S310
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:  # pragma: no cover - depende de la red
        raise RuntimeError(f"No se pudo consultar las tasas: {exc}") from exc

    if data.get("result") != "success":
        raise RuntimeError("La API de tasas no devolvió un resultado válido")

    tasas = data.get("rates", {})
    codigos = {m.codigo for m in db.scalars(select(Moneda)).all()}
    hoy_ = hoy()
    actualizadas = 0

    for codigo, valor in tasas.items():
        if codigo not in codigos or codigo == base:
            continue
        existente = db.scalar(
            select(TasaCambio).where(
                TasaCambio.moneda_origen == base,
                TasaCambio.moneda_destino == codigo,
                TasaCambio.fecha == hoy_,
            )
        )
        if existente is not None:
            existente.tasa = Decimal(str(valor))
            existente.fuente = FUENTE
        else:
            db.add(
                TasaCambio(
                    moneda_origen=base,
                    moneda_destino=codigo,
                    fecha=hoy_,
                    tasa=Decimal(str(valor)),
                    fuente=FUENTE,
                )
            )
        actualizadas += 1

    db.commit()
    return actualizadas
