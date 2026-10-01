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
import re
import uuid
from collections import Counter
from datetime import UTC, date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import archivos, cuotas, ia, limites
from ..clasificador import clasificar, normalizar
from ..config import get_settings
from ..crud_utils import get_owned
from ..defaults import sembrar_etiquetas_diccionario
from ..deps import get_current_user, get_db
from ..embeddings import make_embedding
from ..facturas import (
    aviso_de_la_fecha,
    aviso_del_monto,
    detectar_emisor,
    detectar_fecha,
    detectar_monto,
    es_imagen,
    etiqueta_de_fecha,
    etiqueta_de_valor,
    extraer_texto,
    fecha_de_campo,
    nombre_factura,
    valor_de_campo,
)
from ..impuestos import a_json, detectar_impuestos
from ..lineas import detectar_tipo, parsear_lineas
from ..models import (
    CasoLector,
    Categoria,
    Cuenta,
    Etiqueta,
    Factura,
    FacturaLinea,
    PatronIgnorado,
    PlantillaLector,
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
    CalidadEmisorOut,
    CalidadLectorOut,
    CasoLectorIn,
    CasoLectorOut,
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
    PatronIgnoradoOut,
    PlantillaLectorOut,
    UnificarOut,
)

router = APIRouter(prefix="/facturas", tags=["facturas"])


def _caso_out(caso: CasoLector) -> CasoLectorOut:
    salida = CasoLectorOut.model_validate(caso)
    salida.tiene_archivo = caso.archivo is not None
    return salida


@router.post("/{id}/caso", response_model=CasoLectorOut, status_code=201)
def reportar_caso(
    id: uuid.UUID,
    data: CasoLectorIn,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """«Esta factura la leyó mal»: guarda el caso para poder arreglarlo.

    Se guarda el **texto** y, sobre el mismo texto, lo que dice el lector y con qué se quedó el
    usuario: eso es lo que hace falta para reproducir el fallo y dejarlo como test. El archivo
    original solo se guarda si el usuario lo autoriza.
    """
    factura = get_owned(db, Factura, id, user.id)
    texto = factura.texto_extraido or ""
    if not texto.strip():
        raise HTTPException(
            status_code=400, detail="La factura no tiene texto: no hay nada que revisar."
        )
    lineas = _lineas(db, factura.id)
    caso = CasoLector(
        usuario_id=user.id,
        factura_id=factura.id,
        emisor=factura.emisor,
        emisor_nombre=factura.emisor_nombre,
        texto=texto[:20000],
        tipo_documento=detectar_tipo(texto, lineas) or None,
        # Lo que dice el lector **sobre este texto** (aunque el usuario ya lo haya corregido)
        monto_leido=detectar_monto(texto),
        fecha_leida=detectar_fecha(texto),
        monto_corregido=factura.monto_detectado,
        fecha_corregida=factura.fecha_detectada,
        motivo=(data.motivo or "").strip() or None,
    )
    db.add(caso)
    db.commit()
    db.refresh(caso)
    return _caso_out(caso)


@router.get("/calidad-lector", response_model=CalidadLectorOut)
def calidad_del_lector(
    db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)
):
    """Cómo de bien lee el lector, **por emisor**: sin corrección frente a corregidas.

    Es el panel que dice dónde invertir en vez de adivinar: si un emisor falla siempre, se ataca
    ese; si el 90 % entra solo, el lector está haciendo su trabajo.
    """
    emisor_col = func.coalesce(Factura.emisor, "sin-identificar")
    filas = db.execute(
        select(
            emisor_col.label("emisor"),
            func.max(Factura.emisor_nombre).label("nombre"),
            func.count().label("documentos"),
            func.count().filter(Factura.corregida_en.is_not(None)).label("corregidas"),
            func.count().filter(Factura.leida_con_plantilla.is_(True)).label("con_plantilla"),
            func.max(Factura.creada_en).label("ultima"),
        )
        .where(Factura.usuario_id == user.id)
        .group_by(emisor_col)
        .order_by(func.count().desc())
    ).all()

    # Los casos reportados, por emisor (el buzón es la queja explícita)
    # La misma expresión en el SELECT y en el GROUP BY (si se crea dos veces, SQLAlchemy
    # agrupa por la etiqueta y Postgres lo rechaza)
    emisor_caso = func.coalesce(CasoLector.emisor, "sin-identificar")
    casos = dict(
        db.execute(
            select(emisor_caso, func.count())
            .where(CasoLector.usuario_id == user.id)
            .group_by(emisor_caso)
        ).all()
    )
    abiertos = db.scalar(
        select(func.count())
        .select_from(CasoLector)
        .where(CasoLector.usuario_id == user.id, CasoLector.estado == "abierto")
    )

    emisores = [
        CalidadEmisorOut(
            emisor=f.emisor,
            nombre=f.nombre or f.emisor,
            documentos=f.documentos,
            sin_correccion=f.documentos - f.corregidas,
            corregidas=f.corregidas,
            con_plantilla=f.con_plantilla,
            casos=casos.get(f.emisor, 0),
            ultima=f.ultima,
        )
        for f in filas
    ]
    return CalidadLectorOut(
        emisores=emisores,
        documentos=sum(e.documentos for e in emisores),
        sin_correccion=sum(e.sin_correccion for e in emisores),
        corregidas=sum(e.corregidas for e in emisores),
        con_plantilla=sum(e.con_plantilla for e in emisores),
        casos_abiertos=abiertos or 0,
    )


@router.get("/casos", response_model=list[CasoLectorOut])
def listar_casos(
    estado: str | None = None,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """El buzón: lo que el usuario ha reportado como mal leído."""
    consulta = select(CasoLector).where(CasoLector.usuario_id == user.id)
    if estado:
        consulta = consulta.where(CasoLector.estado == estado)
    casos = db.scalars(consulta.order_by(CasoLector.creado_en.desc())).all()
    return [_caso_out(c) for c in casos]


@router.get("/casos/{caso_id}", response_model=CasoLectorOut)
def ver_caso(
    caso_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    return _caso_out(get_owned(db, CasoLector, caso_id, user.id))


@router.get("/casos/{caso_id}/exportar")
def exportar_caso(
    caso_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """El caso listo para pegarlo como test: el texto tal cual y lo que se espera de él.

    Es el puente entre «esto se leyó mal» y «esto no se vuelve a romper»: lo que hoy se hace a
    mano (mirar el documento, escribir la maqueta, dejarla en `tests/`).
    """
    caso = get_owned(db, CasoLector, caso_id, user.id)
    esperado = caso.monto_corregido if caso.monto_corregido is not None else caso.monto_leido
    nombre = (caso.emisor_nombre or "documento").replace(" ", "_").replace(".", "")[:40]

    def _num(valor) -> str:
        return f"{valor:.2f}".rstrip("0").rstrip(".") if valor is not None else "None"

    triple = chr(34) * 3  # las tres comillas de la maqueta
    lineas = [
        f'"""Caso del buzón: {caso.emisor_nombre or caso.emisor or "sin emisor"}',
        f"Reportado por el usuario el {caso.creado_en:%Y-%m-%d}"
        + (f" · motivo: {caso.motivo}" if caso.motivo else ""),
        '"""',
        "",
        "from decimal import Decimal",
        "",
        f"{nombre.upper()} = {triple}{caso.texto.strip()}{triple}",
        "",
        "",
        f"def test_{nombre.lower()}_se_lee_bien():",
        "    from app.facturas import detectar_monto",
        "",
        f'    assert detectar_monto({nombre.upper()}) == Decimal("{_num(esperado)}")',
    ]
    return {
        "emisor": caso.emisor_nombre or caso.emisor,
        "texto": caso.texto,
        "monto_leido": caso.monto_leido,
        "monto_esperado": esperado,
        "fecha_esperada": caso.fecha_corregida or caso.fecha_leida,
        "motivo": caso.motivo,
        "tiene_archivo": caso.archivo is not None,
        "test": "\n".join(lineas),
    }


@router.get("/casos/{caso_id}/archivo")
def archivo_del_caso(
    caso_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """El documento original del caso (solo existe si el usuario autorizó adjuntarlo)."""
    caso = get_owned(db, CasoLector, caso_id, user.id)
    nombre_archivo = caso.archivo_nombre or "caso"
    if caso.archivo is None:
        raise HTTPException(status_code=404, detail="Este caso no tiene el archivo adjunto")
    return Response(
        content=caso.archivo,
        media_type=caso.archivo_tipo or "application/octet-stream",
        headers={"Content-Disposition": f'inline; filename="{nombre_archivo}"'},
    )


@router.post("/casos/{caso_id}/archivo", response_model=CasoLectorOut)
async def adjuntar_archivo(
    caso_id: uuid.UUID,
    archivo: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """Adjunta el documento original a un caso: es opcional y el usuario lo autoriza aquí.

    Las facturas **no** guardan el archivo (solo el texto), así que si hace falta reproducir el
    fallo con el original, se sube a propósito en este caso.
    """
    caso = get_owned(db, CasoLector, caso_id, user.id)
    contenido = await archivo.read()
    limite = get_settings().tamano_maximo_archivo_mb * 1024 * 1024
    if len(contenido) > limite:
        raise HTTPException(
            status_code=413,
            detail=f"El archivo pesa más de {get_settings().tamano_maximo_archivo_mb} MB.",
        )
    caso.archivo = contenido
    caso.archivo_nombre = archivo.filename or "documento"
    caso.archivo_tipo = archivo.content_type
    db.commit()
    db.refresh(caso)
    return _caso_out(caso)


@router.post("/casos/{caso_id}/resolver", response_model=CasoLectorOut)
def resolver_caso(
    caso_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """Marca el caso como resuelto (ya se arregló y quedó como test)."""
    caso = get_owned(db, CasoLector, caso_id, user.id)
    caso.estado = "resuelto"
    caso.resuelto_en = datetime.now(UTC)
    db.commit()
    db.refresh(caso)
    return _caso_out(caso)


@router.delete("/casos/{caso_id}", status_code=204)
def borrar_caso(
    caso_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    caso = get_owned(db, CasoLector, caso_id, user.id)
    db.delete(caso)
    db.commit()


@router.get("/patrones-ignorados", response_model=list[PatronIgnoradoOut])
def listar_patrones(
    db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)
):
    """Los renglones que el usuario borró y ya se descartan solos."""
    return db.scalars(
        select(PatronIgnorado)
        .where(PatronIgnorado.usuario_id == user.id)
        .order_by(PatronIgnorado.veces.desc(), PatronIgnorado.patron)
    ).all()


@router.delete("/patrones-ignorados/{patron_id}", status_code=204)
def borrar_patron(
    patron_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """Deja de descartar un renglón (si el usuario borró algo que sí era un artículo)."""
    patron = get_owned(db, PatronIgnorado, patron_id, user.id)
    db.delete(patron)
    db.commit()


# Las plantillas van **antes** de `/{id}`: si no, FastAPI toma «plantillas-lector»
# como el id de una factura.
@router.get("/plantillas-lector", response_model=list[PlantillaLectorOut])
def listar_plantillas(
    db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)
):
    """Lo que la app ha aprendido de cada emisor (el usuario puede verlo y borrarlo)."""
    return db.scalars(
        select(PlantillaLector)
        .where(PlantillaLector.usuario_id == user.id)
        .order_by(PlantillaLector.usos.desc(), PlantillaLector.nombre)
    ).all()




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
        # Si ya se aprendió de qué tipo son los documentos de este emisor, manda lo aprendido
        plantilla = _plantilla(db, factura.usuario_id, factura.emisor)
        if plantilla is not None and plantilla.tipo_documento:
            detalle.tipo_documento = plantilla.tipo_documento
    detalle.duplicada = _duplicada(db, factura)
    detalle.aviso_fecha = aviso_de_la_fecha(factura.fecha_detectada, hoy())
    detalle.archivo_guardado = factura.archivo_clave is not None
    detalle.archivo_expira_en = _fecha_del_usuario(factura.archivo_expira_en)
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


# Cuántas veces hay que borrar el mismo renglón para que se descarte solo. Una vez podría ser un
# error; dos es un patrón.
VECES_PARA_IGNORAR = 2


def _patron_de_linea(descripcion: str) -> str | None:
    """El patrón de un renglón que no es artículo: «Cajero: 12» -> «CAJERO».

    Se normaliza (mayúsculas, sin acentos ni códigos) y se quitan los números: lo que cambia en
    cada recibo no puede formar parte del patrón.
    """
    limpio = re.sub(r"\d[\d.,:\-/]*", " ", normalizar(descripcion))
    palabras = [p for p in re.split(r"\s+", limpio) if len(p) > 1][:3]
    patron = " ".join(palabras).strip()
    return patron if len(patron) >= 4 else None


def _ignorados(db: Session, usuario_id: uuid.UUID) -> list[PatronIgnorado]:
    """Los patrones que ya se descartan solos (borrados dos veces o más)."""
    return list(
        db.scalars(
            select(PatronIgnorado).where(
                PatronIgnorado.usuario_id == usuario_id,
                PatronIgnorado.veces >= VECES_PARA_IGNORAR,
            )
        ).all()
    )


def _es_ignorado(descripcion: str, patrones: list[PatronIgnorado]) -> bool:
    plano = re.sub(r"\s+", " ", normalizar(descripcion)).strip()
    return any(plano.startswith(p.patron) for p in patrones)


def _marcar_corregida(factura: Factura) -> None:
    """Deja constancia de que esta lectura hubo que arreglarla (alimenta el panel de calidad)."""
    if factura.corregida_en is None:
        factura.corregida_en = datetime.now(UTC)


def _plantilla(db: Session, usuario_id: uuid.UUID, emisor: str | None) -> PlantillaLector | None:
    if not emisor:
        return None
    return db.scalar(
        select(PlantillaLector).where(
            PlantillaLector.usuario_id == usuario_id, PlantillaLector.emisor == emisor
        )
    )


def _aprender_plantilla(
    db: Session,
    factura: Factura,
    monto: Decimal | None = None,
    fecha: date | None = None,
) -> PlantillaLector | None:
    """Guarda lo aprendido de un emisor cuando el usuario corrige un documento suyo.

    No se guarda el número (cambia en cada factura) sino **en qué etiqueta viene**: «en los
    documentos de este emisor el total está donde dice MONTO». Así, la próxima factura del mismo
    emisor se lee bien a la primera, sin que el usuario vuelva a corregirla.
    """
    emisor = factura.emisor or None
    if not emisor or not factura.texto_extraido:
        return None
    campo_monto = etiqueta_de_valor(factura.texto_extraido, monto) if monto is not None else None
    campo_fecha = etiqueta_de_fecha(factura.texto_extraido) if fecha is not None else None
    if campo_monto is None and campo_fecha is None:
        return None

    plantilla = _plantilla(db, factura.usuario_id, emisor)
    if plantilla is None:
        plantilla = PlantillaLector(
            usuario_id=factura.usuario_id,
            emisor=emisor,
            nombre=factura.emisor_nombre or emisor,
            tipo_documento=detectar_tipo(factura.texto_extraido, _lineas(db, factura.id)) or None,
        )
        db.add(plantilla)
    if campo_monto:
        plantilla.campo_monto = campo_monto
    if campo_fecha:
        plantilla.campo_fecha = campo_fecha
    if factura.emisor_nombre:
        plantilla.nombre = factura.emisor_nombre
    return plantilla


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
        item.aviso_fecha = aviso_de_la_fecha(factura.fecha_detectada, hoy())
        item.archivo_guardado = factura.archivo_clave is not None
        item.archivo_expira_en = _fecha_del_usuario(factura.archivo_expira_en)
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
    # ¿De quién es el documento? Es lo que une las facturas de un mismo emisor para aprender su
    # formato (y para no volver a corregir la misma casa mes a mes).
    emisor_detectado = detectar_emisor(texto) if texto else None
    emisor = emisor_detectado[0] if emisor_detectado else None
    leida_con_plantilla = False
    monto = detectar_monto(texto) if texto else None
    fecha = detectar_fecha(texto) if texto else None
    plantilla = _plantilla(db, user.id, emisor) if emisor else None
    if plantilla is not None and texto:
        # Lo aprendido manda: si el usuario ya dijo dónde está el total en los documentos de
        # este emisor, se busca ahí antes que adivinar.
        del_campo = valor_de_campo(texto, plantilla.campo_monto) if plantilla.campo_monto else None
        if del_campo is not None:
            monto, plantilla.usos, leida_con_plantilla = del_campo, plantilla.usos + 1, True
        if plantilla.campo_fecha:
            del_campo_fecha = fecha_de_campo(texto, plantilla.campo_fecha)
            if del_campo_fecha is not None:
                fecha = del_campo_fecha
    # El QR trae el CUDE/CUFE de la DIAN: no se adivina con OCR
    qr = qr_de_documento(contenido, archivo.filename or "", archivo.content_type)
    cude = cude_de_url(qr)
    factura = Factura(
        usuario_id=user.id,
        nombre_archivo=archivo.filename or "factura.pdf",
        texto_extraido=texto[:20000] if texto else None,
        monto_detectado=monto,
        fecha_detectada=fecha,
        emisor=emisor,
        emisor_nombre=emisor_detectado[1] if emisor_detectado else None,
        leida_con_plantilla=leida_con_plantilla,
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
    db.flush()  # hace falta el id para la clave del archivo
    # Se guarda el archivo para poder releerlo con IA si el lector normal falla. Si el plan no
    # da para más, la factura se sube igual: solo se pierde esa segunda oportunidad.
    guardado, motivo_sin_archivo = archivos.guardar_factura(
        db, factura, user, contenido, archivo.content_type
    )
    db.commit()
    db.refresh(factura)
    salida = FacturaOut.model_validate(factura)
    salida.archivo_guardado = guardado
    salida.archivo_aviso = None if guardado else motivo_sin_archivo
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


@router.delete("/plantillas-lector/{plantilla_id}", status_code=204)
def borrar_plantilla(
    plantilla_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """Borra una plantilla: la próxima factura de ese emisor se vuelve a leer adivinando."""
    plantilla = get_owned(db, PlantillaLector, plantilla_id, user.id)
    db.delete(plantilla)
    db.commit()


def _fecha_del_usuario(momento: datetime | None) -> date | None:
    """La fecha de un instante, en la zona del usuario.

    La caducidad de un archivo se guarda en UTC (el trabajo que lo borra compara en UTC y así no hay
    sorpresas), pero al usuario se le enseña **su** fecha: si no, un archivo que se borra el día 7 se
    le anunciaba como el 8 a partir de las 19:00.
    """
    if momento is None:
        return None
    return momento.astimezone(ZoneInfo(get_settings().timezone)).date()


@router.post("/{id}/leer-con-ia", response_model=FacturaDetalleOut)
async def releer_con_ia(
    id: uuid.UUID,
    contrasena: str | None = Form(None),
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """Relee **esta** factura con el modelo de visión y reemplaza la lectura.

    Es la segunda oportunidad para los documentos que el lector normal no pudo (manuscritos,
    fotos borrosas, formatos raros): se pide a propósito, cuesta una lectura del plan y no crea
    una factura nueva. Lo que ya estaba registrado en un movimiento no se toca.
    """
    factura = get_owned(db, Factura, id, user.id)
    contenido = archivos.contenido_de(factura, contrasena)

    # Igual que en la lectura con IA: se reserva antes de llamar al proveedor
    # Freno de uso: va **antes** de la cuota para que ir rápido no gaste la consulta del plan
    limites.revisar(
        db,
        f"user:{user.id}:lecturas",
        get_settings().limite_lecturas_por_minuto,
        60,
        "las lecturas con IA",
    )
    cuotas.reservar(db, user, cuotas.LECTURA_IA)

    try:
        lectura = ia.leer_documento(
            contenido, factura.nombre_archivo, factura.archivo_tipo, contrasena
        )
    except ia.IaNoConfigurada as error:
        cuotas.devolver(db, user, cuotas.LECTURA_IA)
        raise HTTPException(status_code=503, detail=str(error)) from error
    except Exception as error:  # un fallo del proveedor no se cobra
        cuotas.devolver(db, user, cuotas.LECTURA_IA)
        raise HTTPException(
            status_code=502,
            detail=(
                "El proveedor de IA no pudo leer el documento; no se descontó ninguna lectura "
                f"de tu plan. ({type(error).__name__})"
            ),
        ) from error

    cuotas.registrar_gasto(
        db, user, lectura.tokens_entrada, lectura.tokens_salida, lectura.costo_usd
    )

    campos = lectura.campos
    texto = lectura.texto or factura.texto_extraido or ""
    if texto.strip():
        factura.texto_extraido = texto[:20000]
    monto = ia._decimal(campos.get("monto")) or (detectar_monto(texto) if texto else None)
    factura.monto_detectado = monto
    if campos.get("fecha"):
        fecha_leida = ia.fecha_valida(campos["fecha"])
        if fecha_leida is not None:
            factura.fecha_detectada = fecha_leida
    emisor_detectado = detectar_emisor(texto) if texto else None
    if emisor_detectado:
        factura.emisor, factura.emisor_nombre = emisor_detectado
    if campos.get("emisor"):
        factura.emisor_nombre = str(campos["emisor"])[:140]
    factura.leida_con_ia = True

    # Las líneas del lector que no estaban registradas se reemplazan por las de la IA; lo que el
    # usuario añadió a mano y lo ya confirmado se respeta.
    for linea in _lineas(db, factura.id):
        if linea.transaccion_id is None and linea.origen != "agregada":
            db.delete(linea)
    lineas_ia = campos.get("lineas") or []
    if lineas_ia and detectar_tipo(texto, lineas_ia) not in ("parqueadero", "servicios"):
        for orden, fila in enumerate(lineas_ia):
            valor = ia._decimal(fila.get("valor"))
            if valor is None:
                continue  # sin valor legible no se inventa el artículo
            db.add(
                FacturaLinea(
                    factura_id=factura.id,
                    orden=orden,
                    descripcion=fila["descripcion"],
                    valor_total=valor,
                    origen="ia",
                )
            )
    db.commit()
    db.refresh(factura)
    detalle = _detalle(db, factura)
    avisos = [
        a
        for a in (
            aviso_del_monto(factura.monto_detectado, factura.texto_extraido or ""),
            aviso_de_la_fecha(factura.fecha_detectada, hoy()),
        )
        if a
    ]
    detalle.aviso = " ".join(avisos) or "Leído con IA."
    return detalle


@router.delete("/{id}/archivo", status_code=204)
def borrar_archivo_de_factura(
    id: uuid.UUID,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """Borra el archivo guardado (el usuario manda: la factura y su lectura se quedan)."""
    factura = get_owned(db, Factura, id, user.id)
    archivos.borrar_archivo(db, factura)
    db.commit()


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
    if campos & {"monto_detectado", "fecha_detectada"}:
        _marcar_corregida(factura)
    # Corregir es enseñar: se aprende en qué etiqueta venía el dato bueno, para la próxima
    # factura de este mismo emisor.
    if factura.emisor and factura.emisor_nombre is None:
        emisor_detectado = detectar_emisor(factura.texto_extraido or "")
        if emisor_detectado:
            factura.emisor, factura.emisor_nombre = emisor_detectado
    if factura.emisor:
        _aprender_plantilla(
            db,
            factura,
            monto=data.monto_detectado if "monto_detectado" in campos else None,
            fecha=data.fecha_detectada if "fecha_detectada" in campos else None,
        )
    db.commit()
    db.refresh(factura)
    return _detalle(db, factura)


@router.delete("/{id}", status_code=204)
def eliminar(id: uuid.UUID, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    factura = get_owned(db, Factura, id, user.id)
    # Borrar la factura tiene que borrar también su archivo: si no, queda basura en el disco
    # que nadie reclama y que ya no se puede borrar desde la app.
    archivos.borrar_archivo(db, factura)
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
        _marcar_corregida(factura)
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
    # Y los renglones que el usuario ya borró otras veces (un NIT, el cajero, el cambio) no
    # vuelven a colarse como artículos.
    patrones = _ignorados(db, user.id)
    descartados = [a for a in articulos if _es_ignorado(a["descripcion"], patrones)]
    if descartados:
        articulos = [a for a in articulos if not _es_ignorado(a["descripcion"], patrones)]

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
    avisos = []
    if ya:
        avisos.append(
            f"{len(ya)} de los {len(articulos)} artículos ya estaban dentro de un "
            "movimiento: no se duplicaron."
        )
    if descartados:
        avisos.append(
            f"Se descartaron {len(descartados)} renglón(es) que no son artículos "
            f"({', '.join(sorted({a['descripcion'][:18] for a in descartados}))[:80]})."
        )
    if avisos:
        detalle.aviso = " ".join(avisos)
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

    if data.descripcion is not None or data.valor_total is not None:
        _marcar_corregida(factura)
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
    _marcar_corregida(factura)
    # Borrar un renglón es enseñar: si vuelve a aparecer (y lo vuelve a borrar), se descarta solo.
    patron = _patron_de_linea(linea.descripcion)
    if patron:
        existente = db.scalar(
            select(PatronIgnorado).where(
                PatronIgnorado.usuario_id == user.id, PatronIgnorado.patron == patron
            )
        )
        if existente is None:
            db.add(
                PatronIgnorado(usuario_id=user.id, patron=patron, ejemplo=linea.descripcion[:120])
            )
        else:
            existente.veces += 1
            existente.ejemplo = linea.descripcion[:120]
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

    _marcar_corregida(factura)
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
