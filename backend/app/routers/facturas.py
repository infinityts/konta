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

import json
import uuid
from collections import Counter
from datetime import UTC, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..clasificador import clasificar, normalizar
from ..config import get_settings
from ..crud_utils import get_owned
from ..defaults import sembrar_etiquetas_diccionario
from ..deps import get_current_user, get_db
from ..embeddings import make_embedding
from ..facturas import (
    aviso_del_monto,
    detectar_fecha,
    detectar_monto,
    es_imagen,
    extraer_texto,
    nombre_factura,
)
from ..impuestos import a_json, detectar_impuestos
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
from ..qr import cude_de_url, qr_de_documento
from ..qr import url_dian as url_dian_de_qr
from ..recurrencia import hoy
from ..schemas import (
    ArticuloDetalleOut,
    AsignarEtiquetaIn,
    AsociarFacturaIn,
    AsociarOut,
    ConfirmarLineasIn,
    ConfirmarTotalIn,
    DetalleFacturaOut,
    FacturaDetalleOut,
    FacturaLineaOut,
    FacturaOut,
    FacturaPatchIn,
    GrupoDetalleOut,
    LineaNuevaIn,
    LineasOrdenIn,
    LineaUpdateIn,
    ParsearLineasIn,
    UnificarOut,
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


def _duplicada(db: Session, factura: Factura) -> bool:
    """¿Hay **otra** factura del mismo usuario con el mismo CUDE?

    El CUDE viene del QR, así que dos facturas con el mismo código son el mismo documento
    subido dos veces (o la foto y el PDF oficial de la misma compra).
    """
    if not factura.cude:
        return False
    return bool(
        db.scalar(
            select(func.count())
            .select_from(Factura)
            .where(
                Factura.usuario_id == factura.usuario_id,
                Factura.cude == factura.cude,
                Factura.id != factura.id,
            )
        )
    )


# Margen al comparar el monto de una factura con su transacción: el monto puede venir del
# OCR y redondear. Un peso sobra para el redondeo y no tapa un descuadre de verdad.
TOLERANCIA_FACTURA = Decimal("1")


def _ya_registrados(registradas: list[FacturaLinea], articulos: list[dict]) -> set[int]:
    """Qué artículos de la lectura nueva ya están dentro de un movimiento.

    Volver a leer una factura **no puede duplicar** lo que ya se registró: las líneas con
    movimiento no se borran (el usuario las corrigió y las registró), así que hay que
    saltarse las que repiten. Se empareja **una a una** —dos «BOLSA CANAVERAL» iguales son
    dos líneas, no una— por `(orden, valor)`, que es estable porque el parseo es
    determinista, y por `(descripción, valor)` para el caso de una descripción corregida a
    mano.
    """
    por_orden = Counter((li.orden, li.valor_total) for li in registradas)
    por_texto = Counter((normalizar(li.descripcion), li.valor_total) for li in registradas)
    ya: set[int] = set()
    for i, articulo in enumerate(articulos):
        valor = articulo["valor_total"]
        clave_texto = (normalizar(articulo["descripcion"]), valor)
        if por_orden[(i, valor)] > 0:
            por_orden[(i, valor)] -= 1
            if por_texto[clave_texto] > 0:
                por_texto[clave_texto] -= 1
            ya.add(i)
        elif por_texto[clave_texto] > 0:
            por_texto[clave_texto] -= 1
            ya.add(i)
    return ya


def _detalle(db: Session, factura: Factura) -> FacturaDetalleOut:
    lineas = _lineas(db, factura.id)
    detalle = FacturaDetalleOut.model_validate(factura)
    detalle.lineas = [FacturaLineaOut.model_validate(li) for li in lineas]
    if factura.texto_extraido or lineas:
        detalle.tipo_documento = detectar_tipo(factura.texto_extraido or "", lineas)
    detalle.duplicada = _duplicada(db, factura)
    detalle.aviso_monto = aviso_del_monto(
        factura.monto_detectado,
        factura.texto_extraido or "",
        suma_lineas=sum((li.valor_total for li in lineas), Decimal("0.00")) or None,
    )
    # Auditoría: ¿cuadra con la transacción asociada?
    if factura.transaccion_id:
        tx = db.get(Transaccion, factura.transaccion_id)
        detalle.transaccion_monto = tx.monto if tx else None
        detalle.descuadre = (
            tx.monto - factura.monto_detectado
            if tx is not None and factura.monto_detectado is not None
            else None
        )
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
        regla.actualizada_en = datetime.now(UTC)


# --- facturas -------------------------------------------------------------- #


@router.get("", response_model=list[FacturaOut])
def listar(db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    """Las facturas del usuario, avisando ya desde la lista si el monto no es de fiar.

    Aquí el aviso se calcula **sin** las líneas (sería una consulta por factura): con el texto
    basta para cazar un monto que salió de un número de documento o que es inverosímil, que es
    el caso que deja la factura mintiendo en la lista.
    """
    salida: list[FacturaOut] = []
    for factura in db.scalars(
        select(Factura).where(Factura.usuario_id == user.id).order_by(Factura.creada_en.desc())
    ):
        item = FacturaOut.model_validate(factura)
        item.aviso_monto = aviso_del_monto(
            factura.monto_detectado, factura.texto_extraido or ""
        )
        salida.append(item)
    return salida


@router.post("", response_model=FacturaOut, status_code=201)
async def subir(
    archivo: UploadFile = File(...),
    # Los PDF de factura electrónica suelen venir protegidos (el NIT del emisor)
    contrasena: str | None = Form(None),
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    contenido = await archivo.read()
    limite = get_settings().tamano_maximo_archivo_mb * 1024 * 1024
    if len(contenido) > limite:
        raise HTTPException(
            status_code=413,
            detail=(
                f"El archivo pesa más de {get_settings().tamano_maximo_archivo_mb} MB. "
                "Bájale la calidad a la foto o recórtala y vuelve a intentarlo."
            ),
        )
    if not contenido:
        raise HTTPException(status_code=400, detail="El archivo está vacío")
    if len(contenido) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="El archivo supera 10 MB")

    # El nombre y el tipo son **imprescindibles**: sin ellos `extraer_texto` no sabe que
    # es una foto y la trata como PDF, así que una imagen devolvía texto vacío.
    try:
        texto = extraer_texto(
            contenido, archivo.filename or "", archivo.content_type, contrasena
        )
    except ValueError as error:
        # PDF protegido: se dice, en vez de guardar una factura «sin texto»
        raise HTTPException(status_code=400, detail=str(error)) from error
    impuestos = detectar_impuestos(texto) if texto else None
    # El QR trae el CUDE/CUFE de la DIAN: no se adivina con OCR
    qr = qr_de_documento(contenido, archivo.filename or "", archivo.content_type)
    cude = cude_de_url(qr)
    factura = Factura(
        usuario_id=user.id,
        nombre_archivo=archivo.filename or "factura.pdf",
        texto_extraido=texto[:20000] if texto else None,
        monto_detectado=detectar_monto(texto) if texto else None,
        fecha_detectada=detectar_fecha(texto) if texto else None,
        impuestos_total=impuestos["impuestos_total"] if impuestos else None,
        iva_valor=(
            sum((d["valor"] for d in impuestos["detalle"] if d["nombre"] == "IVA"), Decimal("0"))
            if impuestos
            else None
        ),
        descuento=impuestos["descuento"] if impuestos else None,
        impuestos_detalle=json.dumps(a_json(impuestos)) if impuestos else None,
        cude=cude,
        url_dian=url_dian_de_qr(qr),
    )
    db.add(factura)
    db.commit()
    db.refresh(factura)
    salida = FacturaOut.model_validate(factura)
    salida.duplicada = _duplicada(db, factura)
    return salida


@router.get("/{id}", response_model=FacturaDetalleOut)
def obtener(id: uuid.UUID, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    return _detalle(db, get_owned(db, Factura, id, user.id))


@router.post("/{id}/asociar", response_model=AsociarOut)
def asociar(
    id: uuid.UUID,
    data: AsociarFacturaIn,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    factura = get_owned(db, Factura, id, user.id)
    tx = get_owned(db, Transaccion, data.transaccion_id, user.id)
    factura.transaccion_id = tx.id
    db.commit()
    db.refresh(factura)

    # Auditoría: avisar si no cuadra o si huele a duplicado
    aviso: str | None = None
    descuadre: Decimal | None = None
    if factura.monto_detectado is not None:
        descuadre = tx.monto - factura.monto_detectado
        # Un peso de margen: el monto de la factura muchas veces sale del **OCR** y redondea
        # (los extractos ya lo tenían así). Con comparación exacta, un céntimo de redondeo
        # salía como «no cuadra» y parecía un error de datos.
        if abs(descuadre) > TOLERANCIA_FACTURA:
            aviso = (
                f"La factura es {factura.monto_detectado:,.0f} y esa transacción es "
                f"{tx.monto:,.0f}: no cuadra."
            )
        confirmadas = [
            li.transaccion_id for li in _lineas(db, factura.id) if li.transaccion_id
        ]
        if confirmadas and tx.id not in confirmadas and abs(descuadre) <= TOLERANCIA_FACTURA:
            aviso = (
                "Esta factura ya tiene artículos confirmados y esa transacción es del mismo "
                "valor: parece un duplicado del gasto."
            )
    return AsociarOut(aviso=aviso, descuadre=descuadre)


@router.patch("/{id}", response_model=FacturaDetalleOut)
def corregir(
    id: uuid.UUID,
    data: FacturaPatchIn,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """Corrige el monto y la fecha que detectó el lector.

    Es la otra mitad del paracaídas: puede que el texto esté bien y el **monto** mal (el lector
    tomó un NIT o un consecutivo). Sin esto la factura se queda mintiendo y la auditoría marca
    un descuadre que no existe. Al corregirlo, la auditoría y «Registrar el gasto» usan el
    monto bueno.
    """
    factura = get_owned(db, Factura, id, user.id)
    # Solo lo que venga en la petición: así se puede corregir solo el monto, solo la fecha, o
    # borrar uno de los dos con `null`.
    campos = data.model_fields_set
    if "monto_detectado" in campos:
        factura.monto_detectado = data.monto_detectado
    if "fecha_detectada" in campos:
        factura.fecha_detectada = data.fecha_detectada
    db.commit()
    db.refresh(factura)
    return _detalle(db, factura)


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

    Si llega `texto`, **se guarda como el texto de la factura** y se vuelven a detectar el
    monto y la fecha: es el paracaídas del lector. Cuando el OCR o la extracción se equivocan
    (o el documento viene en un formato que no conocemos), el usuario corrige el texto y
    vuelve a leer, sin depender de que nosotros acertemos.
    """
    factura = get_owned(db, Factura, id, user.id)
    corregido = bool(data and data.texto and data.texto.strip())
    texto = (data.texto if corregido else factura.texto_extraido) or ""
    if corregido:
        factura.texto_extraido = texto
        monto = detectar_monto(texto)
        if monto is not None:
            factura.monto_detectado = monto
        fecha = detectar_fecha(texto)
        if fecha is not None:
            factura.fecha_detectada = fecha
        db.flush()
    if not texto.strip():
        raise HTTPException(
            status_code=400,
            detail=(
                "No pudimos leer el texto de la foto (OCR): prueba con más luz, el recibo "
                "recto y sin sombras, o escribe el total a mano."
                if es_imagen(factura.nombre_archivo)
                else "La factura no tiene texto extraído; súbela de nuevo o envía el texto"
            ),
        )

    # Las líneas que ya están dentro de un movimiento **no se borran** (el usuario las
    # registró) y las que el usuario **añadió a mano** tampoco (no vienen del texto, así que
    # releer no las puede reconstruir). Las demás sí se rehacen: para eso está el releer, y
    # las correcciones de etiqueta se conservan por la regla aprendida en `reglas_ocr`.
    todas = _lineas(db, factura.id)
    registradas = [
        li for li in todas if li.transaccion_id is not None or li.origen == "agregada"
    ]
    for linea in todas:
        if linea.transaccion_id is None and linea.origen != "agregada":
            db.delete(linea)
    db.flush()

    # El diccionario empareja contra **nombres de etiquetas**, así que si a la cuenta le
    # falta alguna (creada antes de que existiera, o borrada), sus productos salían «sin
    # clasificar»: sin `Lácteos y huevos` no había forma de etiquetar la leche. Se
    # completan aquí, solas. Es idempotente: solo crea lo que falta.
    creadas = sembrar_etiquetas_diccionario(db, user.id)
    if creadas:
        db.flush()

    etiquetas = list(
        db.scalars(select(Etiqueta).where(Etiqueta.usuario_id == user.id)).all()
    )
    # Un recibo de **servicio** (parqueadero, factura de servicios) no tiene artículos: su
    # texto es cabecera y pie, y el OCR los convertiría en «artículos» con valores absurdos
    # («Hasta 500000» = $500.000). Se guarda sin detalle y se registra como un solo gasto.
    articulos = parsear_lineas(texto)
    if detectar_tipo(texto, articulos) in ("parqueadero", "servicios"):
        articulos = []

    # Y las que ya estaban registradas se **omiten** en vez de volver a insertarse: era el
    # bug — al releer una factura ya registrada quedaban las 120 viejas más las 120 nuevas.
    ya = _ya_registrados(registradas, articulos)

    emb = make_embedding()
    for orden, articulo in enumerate(articulos):
        if orden in ya:
            continue
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
                iva_tipo=articulo.get("iva_tipo"),
            )
        )
    db.commit()
    db.refresh(factura)
    detalle = _detalle(db, factura)
    if ya:
        detalle.aviso = (
            f"{len(ya)} de los {len(articulos)} artículos ya estaban dentro de un "
            "movimiento: no se duplicaron."
        )
    return detalle


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


@router.post("/{id}/lineas/agregar", response_model=FacturaDetalleOut)
def agregar_linea(
    id: uuid.UUID,
    data: LineaNuevaIn,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """Añade un artículo a mano: el que el lector se saltó.

    Sin esto, una factura a la que le falta un renglón no se podía completar desde la app (y
    el detalle quedaba mintiendo, con una suma que no daba el total).
    """
    factura = get_owned(db, Factura, id, user.id)
    orden = max((li.orden for li in _lineas(db, factura.id)), default=-1) + 1

    if data.etiqueta_id is not None:
        etiqueta = get_owned(db, Etiqueta, data.etiqueta_id, user.id)
        etiqueta_id, origen, confianza = etiqueta.id, "agregada", Decimal("1")
        _aprender(db, user.id, data.descripcion, etiqueta.id)
    else:
        etiquetas = list(db.scalars(select(Etiqueta).where(Etiqueta.usuario_id == user.id)).all())
        # La etiqueta la puede sugerir el clasificador, pero el renglón lo puso el usuario:
        # se marca `agregada` para que un re-parseo no se lo lleve por delante. (`manual`
        # significa otra cosa: una línea del lector cuya etiqueta corrigió el usuario, y esa
        # sí se vuelve a clasificar al releer, que para eso está la regla aprendida.)
        etiqueta_id, _, confianza = clasificar(
            db, user.id, data.descripcion, etiquetas, make_embedding()
        )
        origen = "agregada"

    db.add(
        FacturaLinea(
            factura_id=factura.id,
            orden=orden,
            descripcion=data.descripcion.strip()[:200],
            cantidad=data.cantidad,
            valor_unitario=data.valor_unitario,
            valor_total=data.valor_total,
            etiqueta_id=etiqueta_id,
            origen=origen,
            confianza=confianza,
        )
    )
    db.commit()
    db.refresh(factura)
    return _detalle(db, factura)


@router.put("/{id}/lineas/orden", response_model=FacturaDetalleOut)
def reordenar_lineas(
    id: uuid.UUID,
    data: LineasOrdenIn,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """Reordena las líneas de la factura (el orden en que se muestran y se confirman)."""
    factura = get_owned(db, Factura, id, user.id)
    por_id = {li.id: li for li in _lineas(db, factura.id)}
    desconocidas = [lid for lid in data.linea_ids if lid not in por_id]
    if desconocidas:
        raise HTTPException(status_code=404, detail="Alguna línea no es de esta factura")
    for posicion, linea_id in enumerate(data.linea_ids):
        por_id[linea_id].orden = posicion
    db.commit()
    db.refresh(factura)
    return _detalle(db, factura)


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


class _Pago:
    """De dónde sale el dinero, cuándo y con qué respaldo (lo comparten las dos
    formas de confirmar: una transacción por línea o una sola con el total)."""

    def __init__(self, cuenta_id, tarjeta, fecha, etiquetas, respaldo, categoria_respaldo):
        self.cuenta_id = cuenta_id
        self.tarjeta = tarjeta
        self.fecha = fecha
        self.etiquetas = etiquetas
        self.respaldo = respaldo
        self.categoria_respaldo = categoria_respaldo

    def de_linea(self, linea) -> tuple[uuid.UUID | None, uuid.UUID | None]:
        """`(categoria_id, etiqueta_id)` que le tocan a una línea."""
        etiqueta = self.etiquetas.get(linea.etiqueta_id) if linea.etiqueta_id else None
        if etiqueta is None:
            etiqueta = self.respaldo  # etiqueta elegida para toda la factura
        categoria_id = (
            etiqueta.categoria_id
            if etiqueta is not None
            else self.categoria_respaldo  # categoría elegida para toda la factura
        )
        return categoria_id, (etiqueta.id if etiqueta else None)


def _contexto_de_pago(
    db: Session, user: Usuario, factura: Factura, data: ConfirmarLineasIn | None
) -> _Pago:
    """Valida y resuelve cuenta, tarjeta, fecha y respaldo.

    Si la tarjeta es de **débito**, la transacción hereda su cuenta: una tarjeta de
    débito es un instrumento de esa cuenta, no un saldo aparte.
    """
    cuenta_id = data.cuenta_id if data else None
    if cuenta_id is not None:
        get_owned(db, Cuenta, cuenta_id, user.id)  # valida que sea del usuario

    tarjeta = None
    if data and data.tarjeta_id is not None:
        tarjeta = get_owned(db, Tarjeta, data.tarjeta_id, user.id)
        if tarjeta.tipo == TipoTarjeta.DEBITO and cuenta_id is None:
            cuenta_id = tarjeta.cuenta_id

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
    return _Pago(cuenta_id, tarjeta, fecha, etiquetas, respaldo, categoria_respaldo)


@router.post("/{id}/confirmar", response_model=FacturaDetalleOut)
def confirmar(
    id: uuid.UUID,
    data: ConfirmarLineasIn | None = None,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """Crea una transacción de gasto **por cada línea** pendiente.

    La categoría sale de la etiqueta de la línea (el árbol es
    `Categoría › Etiqueta › Subetiqueta`), así el gasto cae donde debe.

    Se le indica **de dónde sale el dinero** (`tarjeta_id` y/o `cuenta_id`) y la
    **fecha** si el recibo es de otro día.
    """
    factura = get_owned(db, Factura, id, user.id)
    pago = _contexto_de_pago(db, user, factura, data)

    pedidas = set(data.linea_ids) if data and data.linea_ids else None
    pendientes = [
        li
        for li in _lineas(db, factura.id)
        if li.transaccion_id is None and (pedidas is None or li.id in pedidas)
    ]
    if not pendientes:
        raise HTTPException(status_code=400, detail="No hay líneas pendientes de confirmar")

    for linea in pendientes:
        # Un descuento (o un envío gratis) no es un movimiento por sí solo: se queda como
        # detalle de la factura. Si no, se crearía un gasto en negativo.
        if linea.valor_total is None or linea.valor_total <= 0:
            continue
        categoria_id, etiqueta_id = pago.de_linea(linea)
        transaccion = Transaccion(
            usuario_id=user.id,
            tipo=TipoTransaccion.GASTO,
            monto=linea.valor_total,
            moneda=user.moneda_principal,
            fecha=pago.fecha,
            descripcion=linea.descripcion,
            categoria_id=categoria_id,
            etiqueta_id=etiqueta_id,
            cuenta_id=pago.cuenta_id,
            tarjeta_id=pago.tarjeta.id if pago.tarjeta else None,
        )
        db.add(transaccion)
        db.flush()
        linea.transaccion_id = transaccion.id
        if factura.transaccion_id is None:
            factura.transaccion_id = transaccion.id  # compatibilidad con el flujo de 1 gasto

    db.commit()
    db.refresh(factura)
    return _detalle(db, factura)


@router.post("/{id}/confirmar-total", response_model=FacturaDetalleOut)
def confirmar_total(
    id: uuid.UUID,
    data: ConfirmarTotalIn | None = None,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """Cierra el recibo como **una sola** transacción con el total.

    Para una compra de dos o tres cosas, dos o tres movimientos ensucian el listado
    y los reportes. Aquí se crea un único gasto con el total y las líneas quedan
    como **detalle** suyo (todas apuntan a esa transacción), así que se conserva qué
    se compró sin multiplicar los movimientos.

    La categoría y la etiqueta salen del respaldo (`etiqueta_id` o `categoria_id`):
    al ser un solo gasto no hay una etiqueta por línea que heredar. Si no se indica
    `monto`, se usa la suma de las líneas pendientes.
    """
    factura = get_owned(db, Factura, id, user.id)
    pago = _contexto_de_pago(db, user, factura, data)

    todas = _lineas(db, factura.id)
    pendientes = [li for li in todas if li.transaccion_id is None]

    # Un recibo de **servicio** (parqueadero, factura de servicios) no tiene artículos: se
    # registra un único gasto con el total detectado.
    if not todas:
        total_sin_lineas = (data.monto if data and data.monto is not None else None) or factura.monto_detectado
        if total_sin_lineas is None or total_sin_lineas <= 0:
            raise HTTPException(
                status_code=400,
                detail="El recibo no tiene artículos ni un monto legible; corrige el total a mano",
            )
        descripcion_sin_lineas = ((data.descripcion or "").strip() if data else "") or nombre_factura(
            factura.nombre_archivo
        )
        unico = Transaccion(
            usuario_id=user.id,
            tipo=TipoTransaccion.GASTO,
            monto=total_sin_lineas,
            moneda=user.moneda_principal,
            fecha=pago.fecha,
            descripcion=descripcion_sin_lineas,
            categoria_id=pago.categoria_respaldo,
            etiqueta_id=pago.respaldo.id if pago.respaldo is not None else None,
            cuenta_id=pago.cuenta_id,
            tarjeta_id=pago.tarjeta.id if pago.tarjeta else None,
        )
        db.add(unico)
        db.flush()
        factura.transaccion_id = unico.id
        db.commit()
        db.refresh(factura)
        return _detalle(db, factura)

    if not pendientes:
        raise HTTPException(status_code=400, detail="No hay líneas pendientes de confirmar")

    total = data.monto if data and data.monto is not None else sum(
        (li.valor_total for li in pendientes), Decimal("0")
    )
    if total <= 0:
        raise HTTPException(status_code=400, detail="El total del recibo debe ser mayor que cero")

    if data and data.descripcion and data.descripcion.strip():
        descripcion = data.descripcion.strip()
    elif len(pendientes) == 1:
        descripcion = pendientes[0].descripcion
    else:
        descripcion = f"Compra de {len(pendientes)} artículos"

    # Un solo gasto: su categoría sale del respaldo (o de la etiqueta elegida)
    categoria_id = pago.categoria_respaldo
    etiqueta_id = None
    if pago.respaldo is not None:
        etiqueta_id = pago.respaldo.id
        categoria_id = pago.respaldo.categoria_id

    transaccion = Transaccion(
        usuario_id=user.id,
        tipo=TipoTransaccion.GASTO,
        monto=total,
        moneda=user.moneda_principal,
        fecha=pago.fecha,
        descripcion=descripcion,
        categoria_id=categoria_id,
        etiqueta_id=etiqueta_id,
        cuenta_id=pago.cuenta_id,
        tarjeta_id=pago.tarjeta.id if pago.tarjeta else None,
    )
    db.add(transaccion)
    db.flush()

    # Las líneas no se pierden: quedan como detalle de ese único gasto
    for linea in pendientes:
        linea.transaccion_id = transaccion.id
    factura.transaccion_id = transaccion.id

    db.commit()
    db.refresh(factura)
    return _detalle(db, factura)


# --- detalle y unificación de una compra ----------------------------------- #


@router.get("/{id}/detalle", response_model=DetalleFacturaOut)
def detalle_factura(id: uuid.UUID, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    """Artículos de la compra, agrupados por etiqueta con subtotal y porcentaje.

    Es lo que se ve al pulsar «Ver detalle» en el listado: de un solo vistazo, en
    qué etiqueta se fue la plata y qué hay dentro de cada una.
    """
    factura = get_owned(db, Factura, id, user.id)
    lineas = _lineas(db, factura.id)
    total = sum((li.valor_total for li in lineas), Decimal("0"))

    etiquetas = {
        e.id: (e.nombre, e.categoria_id)
        for e in db.scalars(select(Etiqueta).where(Etiqueta.usuario_id == user.id)).all()
    }
    categorias = {
        c.id: c.nombre for c in db.scalars(select(Categoria).where(Categoria.usuario_id == user.id)).all()
    }

    agrupados: dict[uuid.UUID | None, list[FacturaLinea]] = {}
    for li in lineas:
        agrupados.setdefault(li.etiqueta_id, []).append(li)

    grupos: list[GrupoDetalleOut] = []
    for etq_id, arts in agrupados.items():
        sub = sum((a.valor_total for a in arts), Decimal("0"))
        nombre, cat_id = etiquetas.get(etq_id, (None, None))
        grupos.append(
            GrupoDetalleOut(
                etiqueta=nombre,
                categoria=categorias.get(cat_id) if cat_id else None,
                total=sub,
                porcentaje=(sub / total * Decimal(100)).quantize(Decimal("0.1")) if total else Decimal("0"),
                articulos=[
                    ArticuloDetalleOut(
                        id=a.id,
                        descripcion=a.descripcion,
                        cantidad=a.cantidad,
                        valor_unitario=a.valor_unitario,
                        valor_total=a.valor_total,
                        origen=a.origen,
                    )
                    for a in arts
                ],
            )
        )
    grupos.sort(key=lambda g: g.total, reverse=True)

    tx = db.get(Transaccion, factura.transaccion_id) if factura.transaccion_id else None
    desc = (tx.descripcion if tx and tx.descripcion else None) or nombre_factura(factura.nombre_archivo)

    return DetalleFacturaOut(
        factura_id=factura.id,
        descripcion=desc,
        total=total,
        articulos=len(lineas),
        grupos=grupos,
    )


@router.post("/{id}/unificar", response_model=UnificarOut)
def unificar(id: uuid.UUID, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    """Colapsa una factura confirmada línea por línea en **un solo** movimiento.

    El caso del mercado: confirmar 120 artículos creó 120 transacciones. Aquí se
    crea una única transacción con el total (o se reaprovecha la asociada), todas
    las líneas pasan a apuntarle como detalle y se borran las individuales. Así el
    listado muestra una fila y los reportes por etiqueta siguen usando el detalle.
    """
    factura = get_owned(db, Factura, id, user.id)
    lineas = _lineas(db, factura.id)
    if not lineas:
        raise HTTPException(status_code=400, detail="La factura no tiene artículos")

    ids: set[uuid.UUID] = {li.transaccion_id for li in lineas if li.transaccion_id}
    if factura.transaccion_id:
        ids.add(factura.transaccion_id)
    if not ids:
        raise HTTPException(status_code=400, detail="Nada que unificar: confirma primero los artículos")

    txs = [t for t in (db.get(Transaccion, i) for i in ids) if t is not None]
    total = sum((li.valor_total for li in lineas), Decimal("0"))

    # ¿Ya está unificada? (una sola transacción y es la asociada)
    if len(txs) == 1 and factura.transaccion_id == txs[0].id and all(
        li.transaccion_id == txs[0].id for li in lineas
    ):
        return UnificarOut(transaccion_id=txs[0].id, creada=False, unificados=0, total=total)

    # La transacción asociada aporta los metadatos (nombre, categoría, cuenta, tarjeta)
    base = next((t for t in txs if t.id == factura.transaccion_id), None) or txs[0]
    nueva = Transaccion(
        usuario_id=user.id,
        tipo=base.tipo,
        monto=total,
        moneda=base.moneda,
        fecha=factura.fecha_detectada or base.fecha,
        descripcion=(base.descripcion or f"Compra de {len(lineas)} artículos"),
        categoria_id=base.categoria_id,
        etiqueta_id=base.etiqueta_id,
        cuenta_id=base.cuenta_id,
        tarjeta_id=base.tarjeta_id,
        notas=base.notas,
        suscripcion_id=base.suscripcion_id,
        ingreso_recurrente_id=base.ingreso_recurrente_id,
        poliza_id=base.poliza_id,
    )
    db.add(nueva)
    db.flush()

    for li in lineas:
        li.transaccion_id = nueva.id
    factura.transaccion_id = nueva.id

    borradas = 0
    for t in txs:
        if t.id == nueva.id:
            continue
        # No borrar si otra factura la comparte
        otras = db.scalar(
            select(func.count())
            .select_from(FacturaLinea)
            .where(FacturaLinea.transaccion_id == t.id, FacturaLinea.factura_id != factura.id)
        )
        if otras:
            continue
        db.delete(t)
        borradas += 1

    db.commit()
    return UnificarOut(transaccion_id=nueva.id, creada=True, unificados=borradas, total=total)
