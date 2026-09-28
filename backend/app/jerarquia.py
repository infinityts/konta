"""Helpers para la jerarquía de categorías (categoría → subcategoría)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Categoria


def mapa_categorias(db: Session, usuario_id) -> dict:
    """{id: Categoria} de todas las categorías del usuario."""
    return {
        c.id: c
        for c in db.scalars(select(Categoria).where(Categoria.usuario_id == usuario_id)).all()
    }


def ruta_categoria(categoria: Categoria | None, mapa: dict) -> tuple[str, str | None]:
    """Devuelve (categoría raíz, subcategoría | None)."""
    if categoria is None:
        return ("Sin categoría", None)
    if categoria.padre_id and categoria.padre_id in mapa:
        return (mapa[categoria.padre_id].nombre, categoria.nombre)
    return (categoria.nombre, None)
