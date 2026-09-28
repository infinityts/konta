"""Exportar y restaurar los datos de un usuario (respaldo)."""

from __future__ import annotations

import enum
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import Date, DateTime, Enum as SAEnum, Numeric, delete, inspect, select
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Session

from .models import (
    AporteMeta,
    Beneficiario,
    Categoria,
    ConfigNotificaciones,
    Cuenta,
    DeudaTarjeta,
    Etiqueta,
    Factura,
    FacturaLinea,
    IngresoRecurrente,
    ItemLista,
    MetaAhorro,
    Poliza,
    PolizaAsegurado,
    PrecioMercado,
    Presupuesto,
    Producto,
    ReglaOcr,
    Suscripcion,
    Tarjeta,
    Transaccion,
)

# Orden de borrado (hijos primero) y de creación (padres primero).
# `FacturaLinea` no se lista en el borrado: no tiene `usuario_id` y cae por la
# cascada al borrar su factura.
MODELOS_BORRADO = [
    Factura, ReglaOcr, Transaccion, Beneficiario, PolizaAsegurado, Poliza, AporteMeta,
    MetaAhorro, DeudaTarjeta, PrecioMercado, ItemLista, Presupuesto, Suscripcion,
    IngresoRecurrente, Etiqueta, Tarjeta, Categoria, Cuenta, Producto,
    ConfigNotificaciones,
]
MODELOS_CREACION = [
    Categoria, Cuenta, Tarjeta, Producto, Etiqueta, ConfigNotificaciones,
    MetaAhorro, AporteMeta, Poliza, PolizaAsegurado, Beneficiario, Suscripcion,
    IngresoRecurrente, Presupuesto, DeudaTarjeta, PrecioMercado, ItemLista,
    Transaccion, ReglaOcr, Factura, FacturaLinea,
]
NOMBRES = {
    Categoria: "categorias",
    Cuenta: "cuentas",
    Tarjeta: "tarjetas",
    Producto: "productos",
    Etiqueta: "etiquetas",
    ConfigNotificaciones: "config_notificaciones",
    MetaAhorro: "metas_ahorro",
    AporteMeta: "aportes_meta",
    Poliza: "polizas",
    PolizaAsegurado: "poliza_asegurados",
    Beneficiario: "beneficiarios",
    Suscripcion: "suscripciones",
    IngresoRecurrente: "ingresos_recurrentes",
    Presupuesto: "presupuestos",
    DeudaTarjeta: "deudas_tarjeta",
    PrecioMercado: "precios",
    ItemLista: "lista_mercado",
    Transaccion: "transacciones",
    ReglaOcr: "reglas_ocr",
    Factura: "facturas",
    FacturaLinea: "factura_lineas",
}
VERSION = 2


def _dump(obj) -> dict:
    out: dict = {}
    for col in inspect(obj).mapper.column_attrs:
        valor = getattr(obj, col.key)
        if isinstance(valor, enum.Enum):
            valor = valor.value
        out[col.key] = valor
    return out


def _filas_del_usuario(db: Session, modelo, usuario_id) -> list:
    """Filas del usuario. `FacturaLinea` no tiene `usuario_id`: se llega por su factura."""
    if modelo is FacturaLinea:
        return list(
            db.scalars(
                select(FacturaLinea)
                .join(Factura, FacturaLinea.factura_id == Factura.id)
                .where(Factura.usuario_id == usuario_id)
            ).all()
        )
    return list(db.scalars(select(modelo).where(modelo.usuario_id == usuario_id)).all())


def exportar(db: Session, usuario_id) -> dict:
    """Devuelve un dict con todos los datos del usuario (para respaldo)."""
    datos: dict = {"version": VERSION, "exportado_en": datetime.now(timezone.utc).isoformat()}
    for modelo in MODELOS_CREACION:
        datos[NOMBRES[modelo]] = [_dump(f) for f in _filas_del_usuario(db, modelo, usuario_id)]
    return datos


def _convertir(modelo, fila: dict) -> dict:
    """Convierte los valores del JSON a los tipos de columna del modelo."""
    tipos = {c.key: c.columns[0].type for c in inspect(modelo).mapper.column_attrs}
    out: dict = {}
    for clave, valor in fila.items():
        tipo = tipos.get(clave)
        if tipo is None:
            continue
        if valor is None:
            out[clave] = None
        elif isinstance(tipo, SAEnum):
            enum_cls = getattr(tipo, "enum_class", None)
            out[clave] = enum_cls(valor) if enum_cls is not None and not isinstance(valor, enum_cls) else valor
        elif isinstance(tipo, DateTime):
            out[clave] = datetime.fromisoformat(valor) if isinstance(valor, str) else valor
        elif isinstance(tipo, Date):
            out[clave] = date.fromisoformat(valor) if isinstance(valor, str) else valor
        elif isinstance(tipo, Numeric):
            out[clave] = Decimal(str(valor))
        elif isinstance(tipo, PGUUID):
            out[clave] = uuid.UUID(str(valor))
        else:
            out[clave] = valor
    return out


def restaurar(db: Session, usuario_id, datos: dict) -> dict:
    """Reemplaza los datos del usuario por los del respaldo. Devuelve cuántos creó."""
    for modelo in MODELOS_BORRADO:
        db.execute(delete(modelo).where(modelo.usuario_id == usuario_id))
    db.flush()

    creadas: dict[str, int] = {}
    for modelo in MODELOS_CREACION:
        filas = datos.get(NOMBRES[modelo], [])
        if modelo is Etiqueta:
            # Las etiquetas se auto-referencian: primero raíces, luego subetiquetas
            raices = [f for f in filas if not f.get("padre_id")]
            hijas = [f for f in filas if f.get("padre_id")]
            for fila in raices:
                campos = _convertir(Etiqueta, fila)
                campos["usuario_id"] = usuario_id
                db.add(Etiqueta(**campos))
            db.flush()
            for fila in hijas:
                campos = _convertir(Etiqueta, fila)
                campos["usuario_id"] = usuario_id
                db.add(Etiqueta(**campos))
            creadas[NOMBRES[modelo]] = len(filas)
            continue

        for fila in filas:
            campos = _convertir(modelo, fila)
            # `FacturaLinea` cuelga de su factura: no tiene `usuario_id` propio.
            if modelo is not FacturaLinea:
                campos["usuario_id"] = usuario_id  # seguridad: siempre el usuario actual
            db.add(modelo(**campos))
        # Los modelos no declaran `relationship()`, así que el orden de INSERT no
        # se deduce solo: se fuerza un flush por modelo y `MODELOS_CREACION` va de
        # padres a hijos (p. ej. `metas_ahorro` antes de `aportes_meta`).
        db.flush()
        creadas[NOMBRES[modelo]] = len(filas)

    db.commit()
    return creadas
