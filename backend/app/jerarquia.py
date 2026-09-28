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


def copiar_etiquetas(
    db: Session, origen: Categoria, destino: Categoria
) -> tuple[list[Etiqueta], list[str], list[str]]:
    """Copia el árbol de etiquetas de `origen` dentro de `destino`.

    Devuelve `(creadas, omitidas, rutas)`: las etiquetas nuevas, las rutas legibles
    de las que **ya existían** en el destino (no se duplican) y las rutas de las
    creadas. Es **idempotente**: repetirlo no añade nada.

    Si una raíz ya existe en el destino, **sus subetiquetas que falten sí se
    crean**: copiar «Servicios › Internet, Agua» sobre una categoría que ya tiene
    «Servicios» añade las dos hijas, no una segunda «Servicios».

    Copiar (y no compartir la etiqueta entre categorías) es deliberado: aquí una
    etiqueta vive dentro de una categoría y los reportes agrupan por
    `Categoría › Etiqueta › Subetiqueta`, así que compartirla obligaría a decidir
    qué categoría gana en el reporte. Copiando, cada categoría es independiente.
    """
    raices = db.scalars(
        select(Etiqueta)
        .where(
            Etiqueta.usuario_id == origen.usuario_id,
            Etiqueta.categoria_id == origen.id,
            Etiqueta.padre_id.is_(None),
        )
        .order_by(Etiqueta.nombre)
    ).all()

    # Índice (padre_id, nombre en minúsculas) de lo que ya hay en el destino: es la
    # misma clave con la que se valida la unicidad entre hermanos.
    por_padre: dict[tuple, Etiqueta] = {
        (e.padre_id, e.nombre.lower()): e
        for e in db.scalars(
            select(Etiqueta).where(
                Etiqueta.usuario_id == destino.usuario_id,
                Etiqueta.categoria_id == destino.id,
            )
        ).all()
    }

    creadas: list[Etiqueta] = []
    omitidas: list[str] = []
    rutas: list[str] = []

    def copiar_hijas(etq_origen: Etiqueta, etq_destino: Etiqueta, prefijo: str) -> None:
        hijas = db.scalars(
            select(Etiqueta)
            .where(Etiqueta.padre_id == etq_origen.id)
            .order_by(Etiqueta.nombre)
        ).all()
        for hija in hijas:
            ruta = f"{prefijo} › {hija.nombre}"
            clave = (etq_destino.id, hija.nombre.lower())
            actual = por_padre.get(clave)
            if actual is None:
                actual = Etiqueta(
                    usuario_id=destino.usuario_id,
                    categoria_id=destino.id,
                    nombre=hija.nombre,
                    padre_id=etq_destino.id,
                )
                db.add(actual)
                db.flush()  # hace falta el id para colgar sus propias hijas
                por_padre[clave] = actual
                creadas.append(actual)
                rutas.append(ruta)
            else:
                omitidas.append(ruta)
            copiar_hijas(hija, actual, ruta)

    for raiz in raices:
        clave = (None, raiz.nombre.lower())
        actual = por_padre.get(clave)
        if actual is None:
            actual = Etiqueta(
                usuario_id=destino.usuario_id,
                categoria_id=destino.id,
                nombre=raiz.nombre,
            )
            db.add(actual)
            db.flush()
            por_padre[clave] = actual
            creadas.append(actual)
            rutas.append(raiz.nombre)
        else:
            omitidas.append(raiz.nombre)
        copiar_hijas(raiz, actual, raiz.nombre)

    return creadas, omitidas, rutas
