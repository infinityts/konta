"""Helpers del árbol **Categoría → Etiqueta → Subetiqueta**."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Categoria, Etiqueta


def mapa_categorias(db: Session, usuario_id) -> dict:
    """{id: Categoria}"""
    return {
        c.id: c
        for c in db.scalars(select(Categoria).where(Categoria.usuario_id == usuario_id)).all()
    }


def mapa_etiquetas(db: Session, usuario_id) -> dict:
    """{id: Etiqueta}"""
    return {
        e.id: e
        for e in db.scalars(select(Etiqueta).where(Etiqueta.usuario_id == usuario_id)).all()
    }


def ruta_etiqueta(etiqueta: Etiqueta | None, mapa: dict) -> str | None:
    """Devuelve `Etiqueta › Subetiqueta` (o solo la etiqueta, o None)."""
    if etiqueta is None:
        return None
    if etiqueta.padre_id and etiqueta.padre_id in mapa:
        return f"{mapa[etiqueta.padre_id].nombre} › {etiqueta.nombre}"
    return etiqueta.nombre


def etiqueta_completa(categoria: Categoria | None, etiqueta: Etiqueta | None, mapa_etq: dict) -> str:
    """`Categoría › Etiqueta › Subetiqueta` para mostrar."""
    partes = [categoria.nombre if categoria else "Sin categoría"]
    ruta = ruta_etiqueta(etiqueta, mapa_etq)
    if ruta:
        partes.append(ruta)
    return " › ".join(partes)
