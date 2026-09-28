"""Lógica del comparativo de precios de mercado."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import PrecioMercado, Producto


def comparativo(db: Session, usuario_id, producto: Producto) -> dict:
    """Último precio por tienda, ordenado de más barato a más caro."""
    precios = db.scalars(
        select(PrecioMercado)
        .where(
            PrecioMercado.usuario_id == usuario_id,
            PrecioMercado.producto_id == producto.id,
        )
        .order_by(PrecioMercado.fecha.desc())
    ).all()

    ultimos: dict[str, PrecioMercado] = {}
    for p in precios:
        clave = p.tienda or "Sin tienda"
        if clave not in ultimos:
            ultimos[clave] = p

    tiendas = [
        {"tienda": k, "precio": v.precio, "moneda": v.moneda, "fecha": v.fecha}
        for k, v in ultimos.items()
    ]
    tiendas.sort(key=lambda t: float(t["precio"]))

    return {
        "producto_id": producto.id,
        "producto_nombre": producto.nombre,
        "tiendas": tiendas,
        "mas_barata": tiendas[0]["tienda"] if tiendas else None,
    }
