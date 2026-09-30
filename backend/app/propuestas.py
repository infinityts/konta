"""Acciones que el asistente **propone** y el usuario confirma.

La regla que no se negocia: el asistente no cambia nada. Cuando entiende que el usuario quiere
registrar o etiquetar algo, deja una **propuesta** con los datos ya resueltos y validados (la
categoría de verdad, no el nombre que él dijo) y una frase que explica qué va a pasar. Nada se
ejecuta hasta que el usuario confirma, y al confirmar se usa **el mismo camino que la pantalla**
(`app/movimientos.py`), así que el resultado queda igual de bien hecho que a mano.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import movimientos
from .crud_utils import get_owned
from .models import Categoria, Etiqueta, Propuesta, Transaccion, Usuario
from .recurrencia import hoy
from .schemas import TransaccionIn

REGISTRAR = "registrar_movimiento"
ETIQUETAR = "etiquetar_movimiento"


def _texto(valor) -> str:
    return str(valor or "").strip()


def _pesos(valor) -> str:
    """El monto como se escribe en Colombia: $45.000 (puntos de miles, no comas)."""
    return f"{float(valor):,.0f}".replace(",", ".")


def _resolver_categoria(db: Session, usuario: Usuario, nombre: str | None):
    """La categoría por su nombre, tal como la diría una persona."""
    buscado = _texto(nombre)
    if not buscado:
        return None
    filas = db.scalars(
        select(Categoria).where(Categoria.usuario_id == usuario.id, Categoria.nombre.ilike(f"%{buscado}%"))
    ).all()
    if not filas:
        disponibles = [
            c.nombre
            for c in db.scalars(
                select(Categoria).where(Categoria.usuario_id == usuario.id).limit(30)
            ).all()
        ]
        raise HTTPException(
            status_code=422,
            detail=f"No tienes una categoría «{buscado}». Las que tienes: {', '.join(disponibles)}",
        )
    return filas[0]


def _resolver_etiqueta(db: Session, usuario: Usuario, nombre: str | None):
    buscado = _texto(nombre)
    if not buscado:
        return None
    filas = db.scalars(
        select(Etiqueta).where(Etiqueta.usuario_id == usuario.id, Etiqueta.nombre.ilike(f"%{buscado}%"))
    ).all()
    if not filas:
        raise HTTPException(
            status_code=422,
            detail=f"No tienes una etiqueta «{buscado}». Puedes crearla en Organización → Etiquetas.",
        )
    return filas[0]


def _monto(valor) -> Decimal:
    try:
        return Decimal(str(valor).replace(".", "").replace(",", "."))
    except (InvalidOperation, ValueError) as error:
        raise HTTPException(status_code=422, detail=f"«{valor}» no es un monto") from error


def preparar_movimiento(db: Session, usuario: Usuario, datos: dict) -> tuple[str, dict, str]:
    """Valida y resuelve un movimiento propuesto. Devuelve (tipo, datos, resumen)."""
    categoria = _resolver_categoria(db, usuario, datos.get("categoria"))
    etiqueta = _resolver_etiqueta(db, usuario, datos.get("etiqueta"))
    tipo = _texto(datos.get("tipo")).lower() or "gasto"
    if tipo not in ("gasto", "ingreso"):
        raise HTTPException(status_code=422, detail="El tipo tiene que ser gasto o ingreso")

    cuerpo = {
        "tipo": tipo,
        "monto": str(_monto(datos.get("monto"))),
        "fecha": _texto(datos.get("fecha")) or str(hoy()),
        "descripcion": _texto(datos.get("descripcion")) or "Movimiento",
        "categoria_id": str(categoria.id) if categoria else None,
        "etiqueta_id": str(etiqueta.id) if etiqueta else None,
    }
    # Las mismas validaciones de la pantalla: si no pasa aquí, no se propone
    try:
        modelo = TransaccionIn(**cuerpo)
    except ValidationError as error:
        primero = error.errors()[0]
        raise HTTPException(
            status_code=422, detail=f"Dato inválido ({primero['loc'][-1]}): {primero['msg']}"
        ) from error
    limpio = modelo.model_dump()
    movimientos.validar_cuentas(db, usuario, limpio)
    movimientos.validar_referencias(db, usuario, limpio)

    etiqueta_txt = f" · {etiqueta.nombre}" if etiqueta else ""
    categoria_txt = categoria.nombre if categoria else "sin categoría"
    resumen = (
        f"Registrar un {tipo} de ${_pesos(limpio['monto'])} el {limpio['fecha']} "
        f"({limpio['descripcion']}) en {categoria_txt}{etiqueta_txt}"
    )
    return REGISTRAR, {k: (str(v) if v is not None else None) for k, v in limpio.items()}, resumen


def preparar_etiquetado(db: Session, usuario: Usuario, datos: dict) -> tuple[str, dict, str]:
    """Valida y resuelve el etiquetado de un movimiento que ya existe."""
    movimiento = get_owned(db, Transaccion, datos.get("transaccion_id"), usuario.id)
    categoria = _resolver_categoria(db, usuario, datos.get("categoria"))
    etiqueta = _resolver_etiqueta(db, usuario, datos.get("etiqueta"))
    if categoria is None and etiqueta is None:
        raise HTTPException(status_code=422, detail="Hay que decir qué categoría o etiqueta poner")

    cambios = {}
    partes = []
    if categoria is not None:
        cambios["categoria_id"] = str(categoria.id)
        partes.append(f"categoría {categoria.nombre}")
    if etiqueta is not None:
        cambios["etiqueta_id"] = str(etiqueta.id)
        partes.append(f"etiqueta {etiqueta.nombre}")

    resumen = (
        f"Poner {' y '.join(partes)} al movimiento «{movimiento.descripcion}» "
        f"de ${_pesos(movimiento.monto)} del {movimiento.fecha}"
    )
    return ETIQUETAR, {"transaccion_id": str(movimiento.id), **cambios}, resumen


PREPARADORES = {REGISTRAR: preparar_movimiento, ETIQUETAR: preparar_etiquetado}


def proponer(db: Session, usuario: Usuario, tipo: str, datos: dict) -> Propuesta:
    """Deja la propuesta lista para confirmar. **No ejecuta nada.**"""
    preparador = PREPARADORES.get(_texto(tipo))
    if preparador is None:
        raise HTTPException(
            status_code=422,
            detail=f"No sé proponer «{tipo}». Puedo: {', '.join(PREPARADORES)}",
        )
    tipo_final, resueltos, resumen = preparador(db, usuario, datos or {})
    propuesta = Propuesta(
        usuario_id=usuario.id,
        tipo=tipo_final,
        datos=json.dumps(resueltos, ensure_ascii=False),
        resumen=resumen,
    )
    db.add(propuesta)
    db.commit()
    db.refresh(propuesta)
    return propuesta


def _ejecutar_registrar(db: Session, usuario: Usuario, datos: dict) -> str:
    limpio = dict(datos)
    campos = TransaccionIn(**{k: v for k, v in limpio.items() if v is not None}).model_dump()
    campos = {k: v for k, v in campos.items() if v is not None}
    movimientos.validar(campos)
    movimientos.validar_cuentas(db, usuario, campos)
    movimientos.validar_referencias(db, usuario, campos)
    obj = Transaccion(usuario_id=usuario.id, **campos)
    db.add(obj)
    db.flush()
    return f"Movimiento registrado ({obj.fecha}, ${_pesos(obj.monto)})"


def _ejecutar_etiquetar(db: Session, usuario: Usuario, datos: dict) -> str:
    movimiento = get_owned(db, Transaccion, datos.get("transaccion_id"), usuario.id)
    if datos.get("categoria_id"):
        movimiento.categoria_id = datos["categoria_id"]
    if datos.get("etiqueta_id"):
        movimiento.etiqueta_id = datos["etiqueta_id"]
    movimientos.validar_referencias(
        db, usuario, {"categoria_id": movimiento.categoria_id, "etiqueta_id": movimiento.etiqueta_id}
    )
    db.flush()
    return "Movimiento etiquetado"


EJECUTORES = {REGISTRAR: _ejecutar_registrar, ETIQUETAR: _ejecutar_etiquetar}


def confirmar(db: Session, usuario: Usuario, propuesta_id) -> tuple[Propuesta, str, bool]:
    """Ejecuta lo propuesto. **Una sola vez**: si ya estaba confirmada, no repite."""
    propuesta = get_owned(db, Propuesta, propuesta_id, usuario.id)
    if propuesta.estado == "confirmada":
        # Se dice que ya estaba (para que un doble clic no parezca una segunda ejecución) y qué
        # fue lo que quedó hecho
        anterior = (propuesta.resultado or "").strip()
        return propuesta, f"Ya estaba confirmada: {anterior}".strip(), False
    if propuesta.estado == "rechazada":
        raise HTTPException(status_code=409, detail="Esa propuesta ya se descartó")

    ejecutor = EJECUTORES.get(propuesta.tipo)
    if ejecutor is None:
        raise HTTPException(status_code=422, detail="No sé ejecutar esa propuesta")
    try:
        resultado = ejecutor(db, usuario, json.loads(propuesta.datos))
    except HTTPException:
        db.rollback()
        raise
    propuesta.estado = "confirmada"
    propuesta.resultado = resultado
    propuesta.resuelta_en = datetime.now(UTC)
    db.commit()
    db.refresh(propuesta)
    return propuesta, resultado, True


def rechazar(db: Session, usuario: Usuario, propuesta_id) -> Propuesta:
    propuesta = get_owned(db, Propuesta, propuesta_id, usuario.id)
    if propuesta.estado == "pendiente":
        propuesta.estado = "rechazada"
        propuesta.resuelta_en = datetime.now(UTC)
        propuesta.resultado = "Descartada por el usuario"
        db.commit()
        db.refresh(propuesta)
    return propuesta


def pendientes(db: Session, usuario: Usuario) -> list[Propuesta]:
    return list(
        db.scalars(
            select(Propuesta)
            .where(Propuesta.usuario_id == usuario.id, Propuesta.estado == "pendiente")
            .order_by(Propuesta.creada_en.desc())
        ).all()
    )
