"""Facturas PDF: subir, listar, asociar a transacción y eliminar.

Y el flujo de **OCR por línea**: una factura de mercado o un recibo de gasolina no
es un gasto único, son N artículos. Aquí se parte el texto en líneas, se clasifica
cada una contra el árbol de etiquetas del usuario y, al confirmar, se crea **una
transacción por línea**.

    POST   /facturas/{id}/lineas              -> parsea y previsualiza (persiste)
    PATCH  /facturas/{id}/lineas/{linea_id}   -> corrige (y aprende en reglas_ocr)
    DELETE /facturas/{id}/lineas/{linea_id}   -> descarta una línea
    POST   /facturas/{id}/confirmar           -> crea las transacciones
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..clasificador import clasificar, normalizar
from ..crud_utils import get_owned
from ..deps import get_current_user, get_db
from ..embeddings import make_embedding
from ..facturas import detectar_fecha, detectar_monto, extraer_texto
from ..lineas import detectar_tipo, parsear_lineas
from ..models import (
    Categoria,
    Cuenta,
    Etiqueta,
    Factura,
    FacturaLinea,
    ReglaOcr,
    Tarjeta,
    TipoTarjeta,
    TipoTransaccion,
    Transaccion,
    Usuario,
)
from ..recurrencia import hoy
from ..schemas import (
    AsignarEtiquetaIn,
    AsociarFacturaIn,
    ConfirmarLineasIn,
    FacturaDetalleOut,
    FacturaLineaOut,
    FacturaOut,
    LineaUpdateIn,
    ParsearLineasIn,
)

router = APIRouter(prefix="/facturas", tags=["facturas"])


# --- helpers --------------------------------------------------------------- #


def _lineas(db: Session, factura_id: uuid.UUID) -> list[FacturaLinea]:
    return list(
        db.scalars(
            select(FacturaLinea)
            .where(FacturaLinea.factura_id == factura_id)
            .order_by(FacturaLinea.orden, FacturaLinea.creada_en)
        ).all()
    )


def _detalle(db: Session, factura: Factura) -> FacturaDetalleOut:
    lineas = _lineas(db, factura.id)
    detalle = FacturaDetalleOut.model_validate(factura)
    detalle.lineas = [FacturaLineaOut.model_validate(li) for li in lineas]
    if factura.texto_extraido or lineas:
        detalle.tipo_documento = detectar_tipo(factura.texto_extraido or "", lineas)
    return detalle


def _linea_de(db: Session, factura: Factura, linea_id: uuid.UUID) -> FacturaLinea:
    linea = db.scalar(
        select(FacturaLinea).where(
            FacturaLinea.id == linea_id, FacturaLinea.factura_id == factura.id
        )
    )
    if linea is None:
        raise HTTPException(status_code=404, detail="La línea no existe en esta factura")
    return linea


def _aprender(db: Session, usuario_id: uuid.UUID, descripcion: str, etiqueta_id: uuid.UUID) -> None:
    """Guarda/actualiza la regla «este artículo va a esta etiqueta» (nivel historial)."""
    patron = normalizar(descripcion)
    if not patron:
        return
    regla = db.scalar(
        select(ReglaOcr).where(
            ReglaOcr.usuario_id == usuario_id, ReglaOcr.patron == patron
        )
    )
    if regla is None:
        db.add(ReglaOcr(usuario_id=usuario_id, patron=patron, etiqueta_id=etiqueta_id))
    else:
        regla.etiqueta_id = etiqueta_id
        regla.veces_usada += 1
        regla.actualizada_en = datetime.now(timezone.utc)


# --- facturas -------------------------------------------------------------- #


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


@router.get("/{id}", response_model=FacturaDetalleOut)
def obtener(id: uuid.UUID, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    return _detalle(db, get_owned(db, Factura, id, user.id))


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


# --- OCR por línea --------------------------------------------------------- #


@router.post("/{id}/lineas", response_model=FacturaDetalleOut)
def parsear(
    id: uuid.UUID,
    data: ParsearLineasIn | None = None,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """Parte el texto de la factura en artículos y los clasifica.

    Es idempotente: al re-parsear se descartan las líneas anteriores **no
    confirmadas** y se conservan las que ya generaron transacción.
    """
    factura = get_owned(db, Factura, id, user.id)
    texto = (data.texto if data and data.texto else factura.texto_extraido) or ""
    if not texto.strip():
        raise HTTPException(
            status_code=400,
            detail="La factura no tiene texto extraído; súbela de nuevo o envía el texto",
        )

    for linea in _lineas(db, factura.id):
        if linea.transaccion_id is None:
            db.delete(linea)
    db.flush()

    etiquetas = list(
        db.scalars(select(Etiqueta).where(Etiqueta.usuario_id == user.id)).all()
    )
    emb = make_embedding()
    for orden, articulo in enumerate(parsear_lineas(texto)):
        etiqueta_id, origen, confianza = clasificar(
            db, user.id, articulo["descripcion"], etiquetas, emb
        )
        db.add(
            FacturaLinea(
                factura_id=factura.id,
                orden=orden,
                descripcion=articulo["descripcion"],
                cantidad=articulo["cantidad"],
                valor_unitario=articulo["valor_unitario"],
                valor_total=articulo["valor_total"],
                etiqueta_id=etiqueta_id,
                origen=origen,
                confianza=confianza,
            )
        )
    db.commit()
    db.refresh(factura)
    return _detalle(db, factura)


@router.patch("/{id}/lineas/{linea_id}", response_model=FacturaLineaOut)
def editar_linea(
    id: uuid.UUID,
    linea_id: uuid.UUID,
    data: LineaUpdateIn,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """Corrige una línea. Si se asigna etiqueta, se aprende para la próxima factura."""
    factura = get_owned(db, Factura, id, user.id)
    linea = _linea_de(db, factura, linea_id)
    if linea.transaccion_id is not None:
        raise HTTPException(status_code=409, detail="La línea ya generó una transacción")

    if data.descripcion is not None:
        linea.descripcion = data.descripcion
    if data.valor_total is not None:
        linea.valor_total = data.valor_total

    if "etiqueta_id" in data.model_fields_set:
        if data.etiqueta_id is None:
            linea.etiqueta_id = None
            linea.origen = "sin_clasificar"
            linea.confianza = None
        else:
            etiqueta = get_owned(db, Etiqueta, data.etiqueta_id, user.id)
            linea.etiqueta_id = etiqueta.id
            linea.origen = "manual"
            linea.confianza = Decimal("1")
            _aprender(db, user.id, linea.descripcion, etiqueta.id)

    db.commit()
    db.refresh(linea)
    return linea


@router.delete("/{id}/lineas/{linea_id}", status_code=204)
def descartar_linea(
    id: uuid.UUID,
    linea_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    factura = get_owned(db, Factura, id, user.id)
    linea = _linea_de(db, factura, linea_id)
    if linea.transaccion_id is not None:
        raise HTTPException(
            status_code=409,
            detail="La línea ya generó una transacción; borra la transacción primero",
        )
    db.delete(linea)
    db.commit()


@router.patch("/{id}/lineas", response_model=FacturaDetalleOut)
def asignar_etiqueta(
    id: uuid.UUID,
    data: AsignarEtiquetaIn,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """Asigna una etiqueta a **muchas líneas** de una vez (una tira larga, de golpe).

    Cada asignación se aprende en `reglas_ocr`: la próxima compra de lo mismo ya
    se clasifica sola. Por defecto solo toca las líneas **sin clasificar**, para no
    pisar lo que el diccionario acertó.
    """
    factura = get_owned(db, Factura, id, user.id)
    etiqueta = (
        get_owned(db, Etiqueta, data.etiqueta_id, user.id) if data.etiqueta_id else None
    )

    pedidas = set(data.linea_ids) if data.linea_ids else None
    objetivo = [
        li
        for li in _lineas(db, factura.id)
        if li.transaccion_id is None
        and (pedidas is None or li.id in pedidas)
        and (not data.solo_sin_clasificar or li.etiqueta_id is None)
    ]
    if not objetivo:
        raise HTTPException(
            status_code=400, detail="No hay líneas pendientes que encajen con el filtro"
        )

    for linea in objetivo:
        if etiqueta is None:
            linea.etiqueta_id = None
            linea.origen = "sin_clasificar"
            linea.confianza = None
            continue
        linea.etiqueta_id = etiqueta.id
        linea.origen = "manual"
        linea.confianza = Decimal("1")
        _aprender(db, user.id, linea.descripcion, etiqueta.id)

    db.commit()
    db.refresh(factura)
    return _detalle(db, factura)


@router.post("/{id}/confirmar", response_model=FacturaDetalleOut)
def confirmar(
    id: uuid.UUID,
    data: ConfirmarLineasIn | None = None,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """Crea una transacción de gasto por cada línea pendiente.

    La categoría sale de la etiqueta de la línea (el árbol es
    `Categoría › Etiqueta › Subetiqueta`), así el gasto cae donde debe.

    Se le indica **de dónde sale el dinero** (`tarjeta_id` y/o `cuenta_id`) y la
    **fecha** si el recibo es de otro día. Si la tarjeta es de **débito**, la
    transacción hereda su cuenta: una tarjeta de débito es un instrumento de esa
    cuenta, no un saldo aparte.
    """
    factura = get_owned(db, Factura, id, user.id)
    cuenta_id = data.cuenta_id if data else None
    if cuenta_id is not None:
        get_owned(db, Cuenta, cuenta_id, user.id)  # valida que sea del usuario

    tarjeta = None
    if data and data.tarjeta_id is not None:
        tarjeta = get_owned(db, Tarjeta, data.tarjeta_id, user.id)
        if tarjeta.tipo == TipoTarjeta.DEBITO and cuenta_id is None:
            cuenta_id = tarjeta.cuenta_id  # el débito descuenta de su cuenta

    pedidas = set(data.linea_ids) if data and data.linea_ids else None
    pendientes = [
        li
        for li in _lineas(db, factura.id)
        if li.transaccion_id is None and (pedidas is None or li.id in pedidas)
    ]
    if not pendientes:
        raise HTTPException(status_code=400, detail="No hay líneas pendientes de confirmar")

    etiquetas = {
        e.id: e
        for e in db.scalars(select(Etiqueta).where(Etiqueta.usuario_id == user.id)).all()
    }
    # Respaldo para las líneas sin etiqueta: evita gastos sin categoría
    respaldo = etiquetas.get(data.etiqueta_id) if data and data.etiqueta_id else None
    if respaldo is None and data and data.etiqueta_id is not None:
        respaldo = get_owned(db, Etiqueta, data.etiqueta_id, user.id)
    categoria_respaldo = data.categoria_id if data else None
    if categoria_respaldo is not None:
        get_owned(db, Categoria, categoria_respaldo, user.id)

    fecha = (data.fecha if data and data.fecha else None) or factura.fecha_detectada or hoy()

    for linea in pendientes:
        etiqueta = etiquetas.get(linea.etiqueta_id) if linea.etiqueta_id else None
        if etiqueta is None:
            etiqueta = respaldo  # etiqueta elegida para toda la factura
        categoria_id = (
            etiqueta.categoria_id
            if etiqueta is not None
            else categoria_respaldo  # categoría elegida para toda la factura
        )
        transaccion = Transaccion(
            usuario_id=user.id,
            tipo=TipoTransaccion.GASTO,
            monto=linea.valor_total,
            moneda=user.moneda_principal,
            fecha=fecha,
            descripcion=linea.descripcion,
            categoria_id=categoria_id,
            etiqueta_id=etiqueta.id if etiqueta else None,
            cuenta_id=cuenta_id,
            tarjeta_id=tarjeta.id if tarjeta else None,
        )
        db.add(transaccion)
        db.flush()
        linea.transaccion_id = transaccion.id
        if factura.transaccion_id is None:
            factura.transaccion_id = transaccion.id  # compatibilidad con el flujo de 1 gasto

    db.commit()
    db.refresh(factura)
    return _detalle(db, factura)
