"""Extractos bancarios: subida, lectura, análisis y conciliación."""

from __future__ import annotations

import json
import uuid
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..clasificador import clasificar
from ..crud_utils import get_owned
from ..deps import get_current_user, get_db
from ..embeddings import make_embedding
from ..extractos import (
    conciliacion_ok,
    conciliar,
    marcar_informativos,
    parsear,
)
from ..importacion_extractos import (
    comparar_con_el_pago_minimo,
    ejecutar_importacion,
    plan_de_importacion,
    resumen_del_plan,
)
from ..models import (
    Categoria,
    Cuenta,
    Etiqueta,
    Extracto,
    ExtractoMovimiento,
    Moneda,
    Suscripcion,
    Tarjeta,
    Usuario,
)
from ..recurrentes_extractos import detectar as detectar_recurrentes
from ..schemas_extractos import (
    AnalisisOut,
    CandidatoRecurrenteOut,
    CostosDelDineroOut,
    CrearRecurrentesIn,
    CrearRecurrentesOut,
    ExtractoDetalleOut,
    ExtractoOut,
    HallazgoOut,
    ImportarIn,
    ImportarPreviewOut,
    ImportarResultadoOut,
    MovimientoOut,
    ProyeccionOut,
    SimulacionOut,
)
from ..valor_extractos import (
    auditoria as auditar_extracto,
)
from ..valor_extractos import (
    costos_del_dinero,
    proyeccion,
    simulador,
)

router = APIRouter(prefix="/extractos", tags=["extractos"])

EXTENSIONES = (".pdf", ".xlsx", ".xlsm", ".csv")
TAMANO_MAXIMO = 12 * 1024 * 1024


def _moneda_valida(db: Session, codigo: str | None, por_defecto: str = "COP") -> str:
    """La moneda tiene que existir en el catálogo (hay clave foránea)."""
    if not codigo:
        return por_defecto
    codigo = codigo.upper()[:3]
    if db.get(Moneda, codigo) is None:
        return por_defecto
    return codigo


def _clasificar_movimientos(
    db: Session, usuario_id: uuid.UUID, extracto: Extracto, movimientos: list[ExtractoMovimiento]
) -> None:
    """Marca categoría y etiqueta de cada movimiento con el mismo motor del OCR.

    Solo se clasifican las **compras**: un pago, un interés o una comisión no son
    categorías de gasto, y meterlos ensuciaría el desglose.
    """
    etiquetas = list(db.scalars(select(Etiqueta).where(Etiqueta.usuario_id == usuario_id)).all())
    if not etiquetas:
        return
    emb = make_embedding()
    for movimiento in movimientos:
        if movimiento.tipo != "compra" or not movimiento.descripcion:
            continue
        etiqueta_id, origen, confianza = clasificar(
            db, usuario_id, movimiento.descripcion, etiquetas, emb
        )
        if etiqueta_id is None:
            continue
        movimiento.etiqueta_id = etiqueta_id
        movimiento.origen = origen
        etiqueta = db.get(Etiqueta, etiqueta_id)
        if etiqueta is not None:
            movimiento.categoria_id = etiqueta.categoria_id


def _detalle(db: Session, extracto: Extracto) -> ExtractoDetalleOut:
    movimientos = _movimientos(db, extracto.id)
    # `conciliacion` se guarda como texto JSON en la base (una lista de controles) y el
    # esquema la devuelve ya como lista, así que se arma a mano en vez de validar el ORM
    datos = {
        campo: getattr(extracto, campo)
        for campo in ExtractoDetalleOut.model_fields
        if campo not in ("movimientos", "conciliacion")
    }
    datos["movimientos"] = [MovimientoOut.model_validate(m) for m in movimientos]
    datos["conciliacion"] = json.loads(extracto.conciliacion) if extracto.conciliacion else []
    return ExtractoDetalleOut(**datos)


@router.post("", response_model=ExtractoDetalleOut, status_code=201)
def subir_extracto(
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
    archivo: UploadFile = File(...),
    contrasena: str | None = Form(None),
    cuenta_id: uuid.UUID | None = Form(None),
    tarjeta_id: uuid.UUID | None = Form(None),
    tipo: str = Form("tarjeta"),
) -> ExtractoDetalleOut:
    """Sube un extracto (PDF o Excel), lo lee y lo deja listo para revisar.

    **No** crea transacciones: eso es la Fase 2, y solo después de que la conciliación
    cuadre. Aquí solo se lee, se clasifica y se dice si los números cuadran.
    """
    nombre = archivo.filename or "extracto"
    if not nombre.lower().endswith(EXTENSIONES):
        raise HTTPException(400, "Se espera un PDF o un Excel del extracto (.pdf, .xlsx, .csv)")
    contenido = archivo.file.read()
    if not contenido:
        raise HTTPException(400, "El archivo está vacío")
    if len(contenido) > TAMANO_MAXIMO:
        raise HTTPException(400, "El archivo supera los 12 MB")

    if cuenta_id is not None:
        get_owned(db, Cuenta, cuenta_id, user.id)
    if tarjeta_id is not None:
        get_owned(db, Tarjeta, tarjeta_id, user.id)

    try:
        crudo, texto = parsear(contenido, nombre, archivo.content_type, contrasena)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(400, f"No se pudo leer el archivo: {exc}") from exc

    marcar_informativos(crudo)
    checks = conciliar(crudo)

    extracto = Extracto(
        usuario_id=user.id,
        cuenta_id=cuenta_id,
        tarjeta_id=tarjeta_id,
        tipo="cuenta" if tipo == "cuenta" else "tarjeta",
        formato=("xlsx" if nombre.lower().endswith((".xlsx", ".xlsm")) else nombre[-3:].lower()),
        banco=crudo.banco,
        nombre_archivo=nombre[:255],
        moneda=_moneda_valida(db, crudo.moneda),
        periodo_desde=crudo.periodo_desde,
        periodo_hasta=crudo.periodo_hasta,
        fecha_corte=crudo.fecha_corte,
        fecha_pago=crudo.fecha_pago,
        saldo_anterior=crudo.saldo_anterior,
        compras=crudo.compras,
        intereses=crudo.intereses,
        intereses_mora=crudo.intereses_mora,
        otros_cargos=crudo.otros_cargos,
        abonos=crudo.abonos,
        pago_total=crudo.pago_total,
        pago_minimo=crudo.pago_minimo,
        cupo_total=crudo.cupo_total,
        cupo_disponible=crudo.cupo_disponible,
        tasa_mv=crudo.tasa_mv,
        tasa_ea=crudo.tasa_ea,
        conciliacion_ok=conciliacion_ok(checks),
        conciliacion=json.dumps(checks, ensure_ascii=False),
        texto_extraido=texto[:200_000],
    )
    db.add(extracto)
    db.flush()

    movimientos: list[ExtractoMovimiento] = []
    for orden, m in enumerate(crudo.movimientos):
        movimiento = ExtractoMovimiento(
            extracto_id=extracto.id,
            usuario_id=user.id,
            orden=orden,
            fecha=m.fecha,
            descripcion=(m.descripcion or "")[:255],
            valor=m.valor,
            moneda=_moneda_valida(db, m.moneda, extracto.moneda),
            saldo=m.saldo,
            monto_original=m.monto_original,
            moneda_original=_moneda_valida(db, m.moneda_original, "USD") if m.moneda_original else None,
            tasa_cambio=m.tasa_cambio,
            cuotas_n=m.cuotas_n,
            cuotas_total=m.cuotas_total,
            cuota_mes=m.cuota_mes,
            valor_pendiente=m.valor_pendiente,
            tasa_ea=m.tasa_ea,
            titular=m.titular,
            tipo=m.tipo,
            es_informativo=m.es_informativo,
        )
        db.add(movimiento)
        movimientos.append(movimiento)
    db.flush()

    _clasificar_movimientos(db, user.id, extracto, movimientos)
    db.commit()
    db.refresh(extracto)
    return _detalle(db, extracto)


@router.get("", response_model=list[ExtractoOut])
def listar_extractos(
    db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)
) -> list[Extracto]:
    return list(
        db.scalars(
            select(Extracto)
            .where(Extracto.usuario_id == user.id)
            .order_by(Extracto.creado_en.desc())
        ).all()
    )


@router.get("/proyeccion", response_model=ProyeccionOut)
def proyeccion_de_cuotas(
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
    meses: int = Query(12, ge=1, le=60, description="Cuántos meses proyectar"),
) -> ProyeccionOut:
    """Cuánto te toca pagar cada mes por lo que **ya compraste a cuotas**, por moneda.

    Se queda con el último estado de cada compra (el corte más reciente manda) para no
    contar el mismo capital dos veces al tener varios extractos.
    """
    return ProyeccionOut(**proyeccion(db, user.id, meses))


@router.get("/costos", response_model=CostosDelDineroOut)
def costos(
    db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)
) -> CostosDelDineroOut:
    """Lo que te cuesta la deuda: intereses, comisiones e impuestos del corte."""
    return CostosDelDineroOut(**costos_del_dinero(db, user.id))


@router.get("/simulador", response_model=SimulacionOut)
def simular_deuda(
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
    extracto_id: uuid.UUID | None = Query(None),
    pago_mensual: Decimal | None = Query(None, gt=0),
    saldo: Decimal | None = Query(None, gt=0),
) -> SimulacionOut:
    """Simula cuándo terminas de pagar y cuánto pagas de intereses.

    Usa la **tasa real** del extracto (promedio ponderado por capital pendiente) y dice de
    dónde la sacó; si el extracto no la trae, la de la tarjeta.
    """
    extracto = None
    if extracto_id is not None:
        extracto = get_owned(db, Extracto, extracto_id, user.id)
    return SimulacionOut(**simulador(db, user.id, extracto, pago_mensual, saldo))


@router.get("/{extracto_id}", response_model=ExtractoDetalleOut)
def ver_extracto(
    extracto_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
) -> ExtractoDetalleOut:
    extracto = get_owned(db, Extracto, extracto_id, user.id)
    return _detalle(db, extracto)


@router.delete("/{extracto_id}", status_code=204)
def borrar_extracto(
    extracto_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
) -> None:
    extracto = get_owned(db, Extracto, extracto_id, user.id)
    db.delete(extracto)
    db.commit()


@router.get("/{extracto_id}/auditoria", response_model=list[HallazgoOut])
def auditar(
    extracto_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
) -> list[HallazgoOut]:
    """Comprueba que lo que dice el extracto cuadre con lo que hay registrado en Konta."""
    extracto = get_owned(db, Extracto, extracto_id, user.id)
    return [HallazgoOut(**h) for h in auditar_extracto(db, user.id, extracto)]


@router.get("/{extracto_id}/analisis", response_model=AnalisisOut)
def analizar_extracto(
    extracto_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
    moneda: str | None = Query(None, description="Moneda en la que se muestra el análisis"),
) -> AnalisisOut:
    """Análisis del extracto: totales, a dónde se fue la plata, costo del dinero y deuda.

    Los movimientos se guardan **en su moneda** y aquí se muestra el total en la moneda
    elegida, con el desglose por moneda al lado. Nunca se convierte al guardar: la
    conversión es solo de presentación, y si falta la tasa se avisa en vez de inventarla.
    """
    extracto = get_owned(db, Extracto, extracto_id, user.id)
    movimientos = list(
        db.scalars(
            select(ExtractoMovimiento)
            .where(ExtractoMovimiento.extracto_id == extracto.id)
            .order_by(ExtractoMovimiento.orden)
        ).all()
    )
    solicitada = _moneda_valida(db, moneda, extracto.moneda)
    principal = extracto.moneda
    # Convertir de verdad un extracto exige la tasa de cada compra (el TRM del día). Lo
    # que sí se hace: cada movimiento se guarda en su moneda y el desglose por moneda se
    # muestra al lado. Si se pide otra moneda se dice que no se convierte, en vez de
    # mostrar pesos con el símbolo de dólares.
    conversion = solicitada == principal
    elegida = principal

    del_periodo = [m for m in movimientos if not m.es_informativo]
    informativos = [m for m in movimientos if m.es_informativo]

    # Las compras en otra moneda se convierten con **la tasa del propio extracto** (la que
    # se pagó ese día), nunca con una de hoy. Lo que no trae tasa no se convierte: se suma
    # aparte y se lista en `sin_tasa`.
    sin_tasa_total = Decimal("0")

    def total(items: list[ExtractoMovimiento], tipo: str | tuple[str, ...]) -> Decimal:
        nonlocal sin_tasa_total
        tipos = (tipo,) if isinstance(tipo, str) else tipo
        acumulado = Decimal("0")
        for m in items:
            if m.tipo not in tipos:
                continue
            if m.moneda == principal:
                acumulado += abs(m.valor)
            elif m.tasa_cambio:
                acumulado += abs(m.valor) * m.tasa_cambio
            else:
                sin_tasa_total += abs(m.valor)
        return acumulado

    compras = total(del_periodo, "compra").quantize(Decimal("0.01"))
    pagos = total(del_periodo, ("pago", "ajuste")).quantize(Decimal("0.01"))
    intereses = total(del_periodo, "interes") + (extracto.intereses or Decimal("0"))
    comisiones = total(del_periodo, ("comision", "impuesto"))
    costos = intereses + comisiones

    por_moneda: dict[str, dict[str, Decimal | int]] = {}
    for m in del_periodo:
        fila = por_moneda.setdefault(
            m.moneda,
            {"compras": Decimal("0"), "pagos": Decimal("0"), "movimientos": 0, "pendiente": Decimal("0")},
        )
        if m.tipo == "compra":
            fila["compras"] += m.valor
        if m.tipo in ("pago", "ajuste"):
            fila["pagos"] += abs(m.valor)
        fila["movimientos"] += 1
        if m.valor_pendiente:
            fila["pendiente"] += m.valor_pendiente

    # A dónde se fue la plata: por etiqueta, y agrupado por categoría
    por_categoria: dict[str, dict[str, Decimal | list[str]]] = {}
    for m in del_periodo:
        if m.tipo != "compra" or m.moneda != principal:
            continue
        etiqueta = db.get(Etiqueta, m.etiqueta_id) if m.etiqueta_id else None
        categoria = db.get(Categoria, etiqueta.categoria_id) if etiqueta else None
        nombre = categoria.nombre if categoria else "Sin categoría"
        fila = por_categoria.setdefault(nombre, {"total": Decimal("0"), "etiquetas": []})
        fila["total"] += m.valor
        if etiqueta and etiqueta.nombre not in fila["etiquetas"]:
            fila["etiquetas"].append(etiqueta.nombre)

    # Compromiso futuro: capital de las compras a cuotas que queda por pagar
    compromiso: dict[str, Decimal] = {}
    for m in movimientos:
        if m.valor_pendiente:
            compromiso[m.moneda] = compromiso.get(m.moneda, Decimal("0")) + m.valor_pendiente

    cupo_utilizado = None
    if extracto.cupo_total is not None and extracto.cupo_disponible is not None:
        # El declarado manda: `total - disponible` es la comprobación, no la fuente
        cupo_utilizado = (
            extracto.cupo_utilizado
            if extracto.cupo_utilizado is not None
            else extracto.cupo_total - extracto.cupo_disponible
        )

    sin_tasa = [
        {
            "fecha": m.fecha.isoformat() if m.fecha else None,
            "descripcion": m.descripcion,
            "moneda": m.moneda,
            "valor": str(m.valor),
        }
        for m in del_periodo
        if m.moneda != principal and m.tasa_cambio is None
    ]

    avisos = _avisos(extracto, movimientos)
    if not conversion:
        avisos.append(
            f"Los totales van en {principal}, la moneda del extracto: convertir a {solicitada} "
            "necesita la tasa de cada compra"
        )
    if sin_tasa:
        avisos.append(
            f"{len(sin_tasa)} movimiento(s) en otra moneda sin tasa de cambio en el extracto: "
            "no se convierten (por eso el total en "
            f"{principal} no los incluye)"
        )

    return AnalisisOut(
        extracto_id=extracto.id,
        moneda=elegida,
        moneda_extracto=principal,
        moneda_solicitada=solicitada,
        conversion_aplicada=conversion,
        conciliacion_ok=extracto.conciliacion_ok,
        conciliacion=json.loads(extracto.conciliacion) if extracto.conciliacion else [],
        compras=compras,
        pagos=pagos,
        intereses=intereses,
        comisiones=comisiones,
        costos_financieros=costos,
        movimientos=len(del_periodo),
        movimientos_informativos=len(informativos),
        por_moneda=por_moneda,
        por_categoria=[
            {"categoria": k, "total": v["total"], "etiquetas": v["etiquetas"]}
            for k, v in sorted(por_categoria.items(), key=lambda kv: kv[1]["total"], reverse=True)
        ],
        compromiso_futuro=compromiso,
        cupo_total=extracto.cupo_total,
        cupo_disponible=extracto.cupo_disponible,
        cupo_utilizado=cupo_utilizado,
        pago_total=extracto.pago_total,
        pago_minimo=extracto.pago_minimo,
        intereses_declarados=extracto.intereses,
        sin_tasa_total=sin_tasa_total.quantize(Decimal("0.01")),
        avisos=avisos,
        sin_tasa=sin_tasa,
    )


def _movimientos(db: Session, extracto_id: uuid.UUID) -> list[ExtractoMovimiento]:
    return list(
        db.scalars(
            select(ExtractoMovimiento)
            .where(ExtractoMovimiento.extracto_id == extracto_id)
            .order_by(ExtractoMovimiento.orden)
        ).all()
    )


@router.get("/{extracto_id}/recurrentes", response_model=list[CandidatoRecurrenteOut])
def detectar_recurrentes_del_extracto(
    extracto_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
) -> list[CandidatoRecurrenteOut]:
    """Posibles suscripciones y gastos recurrentes, con la evidencia de cada uno.

    Mira **todos** tus extractos (la repetición entre cortes es la señal fuerte) y también
    tus movimientos, así que sirve aunque solo tengas un extracto leído. Una compra a
    cuotas nunca se propone: es un pago troceado, no una suscripción.
    """
    extracto = get_owned(db, Extracto, extracto_id, user.id)
    return [
        CandidatoRecurrenteOut.model_validate(c)
        for c in detectar_recurrentes(db, user.id, extracto.id)
    ]


@router.post("/{extracto_id}/recurrentes", response_model=CrearRecurrentesOut)
def crear_recurrentes_del_extracto(
    extracto_id: uuid.UUID,
    data: CrearRecurrentesIn,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
) -> CrearRecurrentesOut:
    """Crea los recurrentes elegidos de la lista de candidatos.

    Se eligen por **clave**: el servidor vuelve a detectar y crea desde sus propios datos.
    Las que ya existían con ese nombre se omiten, para no duplicar.
    """
    extracto = get_owned(db, Extracto, extracto_id, user.id)
    if data.cuenta_id is not None:
        get_owned(db, Cuenta, data.cuenta_id, user.id)
    if data.categoria_id is not None:
        get_owned(db, Categoria, data.categoria_id, user.id)
    if data.etiqueta_id is not None:
        get_owned(db, Etiqueta, data.etiqueta_id, user.id)

    candidatos = {
        c.clave: c for c in detectar_recurrentes(db, user.id, extracto.id)
    }
    existentes = {
        s.nombre.strip().lower()
        for s in db.scalars(select(Suscripcion).where(Suscripcion.usuario_id == user.id)).all()
    }

    creadas: list[Suscripcion] = []
    omitidas: list[str] = []
    for clave in data.claves:
        candidato = candidatos.get(clave)
        if candidato is None:
            omitidas.append(f"{clave}: ya no está entre los candidatos")
            continue
        if candidato.nombre.strip().lower() in existentes:
            omitidas.append(f"{candidato.nombre}: ya estaba en tus recurrentes")
            continue
        suscripcion = Suscripcion(
            usuario_id=user.id,
            nombre=candidato.nombre[:120],
            monto=candidato.monto,
            moneda=candidato.moneda,
            periodicidad=candidato.periodicidad,
            fecha_inicio=(
                date.fromisoformat(candidato.fechas[0]) if candidato.fechas else candidato.ultima_fecha
            ),
            proximo_pago=candidato.proximo_pago,
            categoria_id=data.categoria_id or candidato.categoria_id,
            etiqueta_id=data.etiqueta_id or candidato.etiqueta_id,
            cuenta_id=data.cuenta_id or extracto.cuenta_id,
            tarjeta_id=extracto.tarjeta_id,
            notas=(
                f"Detectado en el extracto «{extracto.nombre_archivo}». "
                + " · ".join(candidato.senales)
            )[:2000],
        )
        db.add(suscripcion)
        creadas.append(suscripcion)
        existentes.add(candidato.nombre.strip().lower())
    db.commit()
    for s in creadas:
        db.refresh(s)
    return CrearRecurrentesOut(creadas=creadas, omitidas=omitidas)


@router.get("/{extracto_id}/importar", response_model=ImportarPreviewOut)
def previsualizar_importacion(
    extracto_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
    incluir_cuotas_anteriores: bool = Query(
        True, description="Incluir la cuota de este mes de compras de meses anteriores"
    ),
) -> ImportarPreviewOut:
    """Qué se importaría: la **cuota del mes** como gasto y lo que se omite, con el porqué.

    La previsualización y la importación usan **el mismo plan**, así que lo que ves es
    exactamente lo que se crea.
    """
    extracto = get_owned(db, Extracto, extracto_id, user.id)
    lineas = plan_de_importacion(
        _movimientos(db, extracto.id), extracto, incluir_cuotas_anteriores
    )
    resumen = resumen_del_plan(lineas)
    diferencia, nota = comparar_con_el_pago_minimo(resumen, extracto)
    return ImportarPreviewOut(
        extracto_id=extracto.id,
        lineas=lineas,  # type: ignore[arg-type]
        resumen=resumen,
        pago_minimo=extracto.pago_minimo,
        diferencia_pago_minimo=diferencia,
        nota_pago_minimo=nota,
    )


@router.post("/{extracto_id}/importar", response_model=ImportarResultadoOut)
def importar_extracto(
    extracto_id: uuid.UUID,
    data: ImportarIn | None = None,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
) -> ImportarResultadoOut:
    """Crea las transacciones del periodo del extracto.

    Se le dice **de dónde sale el dinero** (`tarjeta_id` y/o `cuenta_id`). Si la tarjeta
    es de débito, la transacción hereda su cuenta. Los movimientos ya importados no se
    repiten: se puede pulsar dos veces sin duplicar nada.
    """
    extracto = get_owned(db, Extracto, extracto_id, user.id)
    cuenta_id = data.cuenta_id if data else None
    tarjeta_id = data.tarjeta_id if data else None
    if cuenta_id is not None:
        get_owned(db, Cuenta, cuenta_id, user.id)
    tarjeta = None
    if tarjeta_id is not None:
        tarjeta = get_owned(db, Tarjeta, tarjeta_id, user.id)
        if tarjeta.tipo == "debito" and cuenta_id is None:
            cuenta_id = tarjeta.cuenta_id

    resultado = ejecutar_importacion(
        db,
        user.id,
        extracto,
        _movimientos(db, extracto.id),
        cuenta_id=cuenta_id,
        tarjeta_id=tarjeta_id,
        incluir_cuotas_anteriores=(data.incluir_cuotas_anteriores if data else True),
    )
    db.commit()
    return ImportarResultadoOut(extracto_id=extracto.id, **resultado)


def _avisos(extracto: Extracto, movimientos: list[ExtractoMovimiento]) -> list[str]:
    """Avisos para el usuario: lo que hay que mirar antes de importar."""
    avisos: list[str] = []
    if not extracto.conciliacion_ok:
        avisos.append("La conciliación no cuadra: revisa los controles antes de importar")
    if not movimientos:
        avisos.append("No se reconoció ningún movimiento en el archivo")
    if any(m.moneda != extracto.moneda for m in movimientos):
        avisos.append("El extracto trae movimientos en más de una moneda: se muestran por separado")
    if not extracto.periodo_desde or not extracto.periodo_hasta:
        avisos.append("No se pudo leer el periodo facturado: se importará todo el detalle")
    return avisos
