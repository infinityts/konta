"""Categorías y etiquetas por defecto para usuarios nuevos."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Categoria, Etiqueta

DEFAULT_CATEGORIAS: list[dict] = [
    # gastos
    {"nombre": "Suscripciones", "tipo": "gasto", "icono": "repeat", "color": "#6366f1"},
    {"nombre": "Mercado", "tipo": "gasto", "icono": "cart", "color": "#22c55e"},
    {"nombre": "Transporte", "tipo": "gasto", "icono": "car", "color": "#f59e0b"},
    {"nombre": "Vivienda", "tipo": "gasto", "icono": "home", "color": "#0ea5e9"},
    {"nombre": "Restaurantes", "tipo": "gasto", "icono": "utensils", "color": "#ef4444"},
    {"nombre": "Salud", "tipo": "gasto", "icono": "heart", "color": "#ec4899"},
    {"nombre": "Entretenimiento", "tipo": "gasto", "icono": "gamepad", "color": "#a855f7"},
    {"nombre": "Telefonía", "tipo": "gasto", "icono": "phone", "color": "#0891b2"},
    {"nombre": "Otros gastos", "tipo": "gasto", "icono": "ellipsis", "color": "#64748b"},
    # ingresos
    {"nombre": "Salario", "tipo": "ingreso", "icono": "wallet", "color": "#10b981"},
    {"nombre": "Otros ingresos", "tipo": "ingreso", "icono": "plus", "color": "#14b8a6"},
]

# Etiquetas que el **diccionario del OCR** (`clasificador.DICCIONARIO`) sabe
# reconocer, colocadas en la categoría donde tienen sentido. Sin ellas, el
# clasificador no tiene con qué comparar y toda tira de mercado sale
# «sin clasificar»: el diccionario empareja contra **nombres de etiquetas**.
#
# La coherencia con el diccionario la vigila un test: si alguien añade una
# etiqueta aquí que el diccionario no conoce, ese test falla.
ETIQUETAS_DICCIONARIO: dict[str, list[str]] = {
    "Mercado": [
        "Carnes",
        "Frutas y verduras",
        "Lácteos y huevos",
        "Despensa",
        "Aseo del hogar",
        "Cuidado personal",
    ],
    "Transporte": ["Gasolina"],
    # El diccionario también reconoce ropa, calzado y tecnología, y no hay una
    # categoría propia para ellos: «Otros gastos» es el cajón correcto.
    "Otros gastos": ["Ropa", "Calzado", "Tecnología"],
}


def sembrar_etiquetas_diccionario(db: Session, usuario_id) -> list[Etiqueta]:
    """Crea las etiquetas del diccionario que le falten al usuario.

    Se usa al registrar y desde `POST /etiquetas/diccionario`, para quien ya tenía
    cuenta antes de que existieran. Es **idempotente**: solo añade lo que falta, y
    no toca nada si el usuario renombró o borró la categoría de destino.
    """
    categorias = {
        c.nombre: c
        for c in db.scalars(select(Categoria).where(Categoria.usuario_id == usuario_id)).all()
    }
    existentes = {
        (e.categoria_id, e.nombre.lower())
        for e in db.scalars(
            select(Etiqueta).where(
                Etiqueta.usuario_id == usuario_id, Etiqueta.padre_id.is_(None)
            )
        ).all()
    }
    creadas: list[Etiqueta] = []
    for nombre_categoria, nombres in ETIQUETAS_DICCIONARIO.items():
        categoria = categorias.get(nombre_categoria)
        if categoria is None:
            continue
        for nombre in nombres:
            if (categoria.id, nombre.lower()) in existentes:
                continue
            etiqueta = Etiqueta(
                usuario_id=usuario_id, categoria_id=categoria.id, nombre=nombre
            )
            db.add(etiqueta)
            creadas.append(etiqueta)
            existentes.add((categoria.id, nombre.lower()))
    return creadas
