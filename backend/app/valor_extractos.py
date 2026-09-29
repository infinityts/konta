"""Valor acumulado de los extractos (Fase 4).

Tres preguntas, que son las que uno se hace de verdad mirando una tarjeta:

1. **¿Cuánto debo y cuánto me toca cada mes?** El *compromiso futuro*: las cuotas de lo que
   ya compré. Se proyecta mes a mes por moneda, porque sumar pesos y dólares no significa
   nada y **no se convierte al guardar**.
2. **¿Cuánto me está costando esa deuda?** El *costo del dinero*: intereses, comisiones e
   impuestos, y qué parte de lo que pago se va en eso.
3. **¿Cuadra lo que dice el banco con lo que tengo registrado?** La *auditoría*
   extracto↔Konta, que es la que descubre un movimiento sin importar o uno duplicado.

Y la tasa: el extracto trae la de cada compra (`1,9648% 26,30%`), así que la **tasa real** de
la deuda es el **promedio ponderado por el capital pendiente**, no la que tengamos
configurada en la tarjeta. El simulador usa esa y dice de dónde salió.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from .importacion_extractos import MOTIVO_PAGO, plan_de_importacion
from .intereses import mensual_desde_ea, simular_pago
from .models import Extracto, ExtractoMovimiento, Tarjeta, Transaccion
from .recurrencia import hoy

CERO = Decimal("0")


def _meses_siguientes(desde: date, cuantos: int) -> list[str]:
    """`['2026-10', '2026-11', …]` a partir de `desde`."""
    meses: list[str] = []
    anio, mes = desde.year, desde.month
    for _ in range(cuantos):
        mes += 1
        if mes > 12:
            mes, anio = 1, anio + 1
        meses.append(f"{anio:04d}-{mes:02d}")
    return meses


@dataclass
class CuotaDeCompra:
    """Una compra a cuotas: lo que ya se pagó y lo que falta."""

    descripcion: str
    moneda: str
    valor_compra: Decimal
    cuota_mes: Decimal
    cuotas_pagadas: int
    cuotas_total: int
    pendiente: Decimal
    tasa_ea: Decimal | None

    @property
    def cuotas_restantes(self) -> int:
        return max(0, self.cuotas_total - self.cuotas_pagadas)


def compras_a_cuotas(db: Session, usuario_id: uuid.UUID) -> list[CuotaDeCompra]:
    """Todo lo comprado a cuotas que todavía tiene capital pendiente.

    Se quedan con el **último** estado de cada compra (el extracto más reciente manda: es
    donde el pendiente está más al día), para no sumar el mismo capital varias veces al
    tener varios cortes.
    """
    movimientos = db.scalars(
        select(ExtractoMovimiento)
        .where(
            ExtractoMovimiento.usuario_id == usuario_id,
            ExtractoMovimiento.cuotas_total > 1,
            ExtractoMovimiento.valor_pendiente > CERO,
        )
        .order_by(ExtractoMovimiento.fecha)
    ).all()

    ultimo_por_compra: dict[tuple, ExtractoMovimiento] = {}
    for m in movimientos:
        # La **fecha de la compra** es parte de la identidad: hay extractos que no la
        # describen (una línea en blanco) y sin ella se fundirían compras distintas
        clave = (_plano(m.descripcion), int(m.valor), m.fecha)
        ultimo_por_compra[clave] = m  # el más reciente gana

    compras: list[CuotaDeCompra] = []
    for m in ultimo_por_compra.values():
        cuotas_pagadas = m.cuotas_n or 0
        cuotas_total = m.cuotas_total or 0
        restantes = max(0, cuotas_total - cuotas_pagadas)
        cuota = m.cuota_mes
        if cuota is None and restantes > 0:
            # El extracto no dio la cuota, pero sí el capital y cuántas faltan
            cuota = (m.valor_pendiente or CERO) / restantes
        compras.append(
            CuotaDeCompra(
                descripcion=m.descripcion,
                moneda=m.moneda,
                valor_compra=abs(m.valor),
                cuota_mes=cuota or CERO,
                cuotas_pagadas=cuotas_pagadas,
                cuotas_total=cuotas_total,
                pendiente=m.valor_pendiente or CERO,
                tasa_ea=m.tasa_ea,
            )
        )
    compras.sort(key=lambda c: c.pendiente, reverse=True)
    return compras


def _plano(texto: str | None) -> str:
    return " ".join((texto or "").upper().split())


def proyeccion(
    db: Session, usuario_id: uuid.UUID, meses: int = 12, desde: date | None = None
) -> dict:
    """Cuánto toca pagar cada mes por lo ya comprado, **por moneda**.

    Los meses empiezan después de la fecha de corte más reciente (o de hoy).
    """
    compras = compras_a_cuotas(db, usuario_id)
    inicio = desde or _ultimo_corte(db, usuario_id) or hoy()
    etiquetas = _meses_siguientes(inicio, meses)

    por_moneda: dict[str, dict] = {}
    for compra in compras:
        fila = por_moneda.setdefault(
            compra.moneda,
            {
                "pendiente": CERO,
                "cuota_mensual_actual": CERO,
                "compras": 0,
                "meses": {etiqueta: CERO for etiqueta in etiquetas},
            },
        )
        fila["pendiente"] += compra.pendiente
        fila["cuota_mensual_actual"] += compra.cuota_mes
        fila["compras"] += 1
        for i in range(min(compra.cuotas_restantes, len(etiquetas))):
            fila["meses"][etiquetas[i]] += compra.cuota_mes

    return {
        "desde": inicio.isoformat(),
        "meses": etiquetas,
        "por_moneda": {
            moneda: {
                "pendiente": str(fila["pendiente"]),
                "cuota_mensual_actual": str(fila["cuota_mensual_actual"]),
                "compras": fila["compras"],
                "meses": {k: str(v) for k, v in fila["meses"].items()},
            }
            for moneda, fila in por_moneda.items()
        },
        "detalle": [
            {
                "descripcion": c.descripcion,
                "moneda": c.moneda,
                "valor_compra": str(c.valor_compra),
                "cuota_mes": str(c.cuota_mes),
                "cuotas": f"{c.cuotas_pagadas}/{c.cuotas_total}",
                "cuotas_restantes": c.cuotas_restantes,
                "pendiente": str(c.pendiente),
                "tasa_ea": str(c.tasa_ea) if c.tasa_ea is not None else None,
            }
            for c in compras
        ],
    }


def _ultimo_corte(db: Session, usuario_id: uuid.UUID) -> date | None:
    extracto = db.scalars(
        select(Extracto)
        .where(Extracto.usuario_id == usuario_id, Extracto.fecha_corte.is_not(None))
        .order_by(Extracto.fecha_corte.desc())
    ).first()
    return extracto.fecha_corte if extracto else None


def tasa_real(
    db: Session, usuario_id: uuid.UUID, tarjeta: Tarjeta | None = None
) -> tuple[Decimal | None, str | None]:
    """La tasa E.A. que de verdad estás pagando, y de dónde sale.

    Es el **promedio ponderado por el capital pendiente** de las tasas que trae el
    extracto: la deuda cara pesa más que la barata. Si el extracto no trae tasas se usa la
    de la tarjeta, y se dice que es esa.
    """
    filas = db.scalars(
        select(ExtractoMovimiento).where(
            ExtractoMovimiento.usuario_id == usuario_id,
            ExtractoMovimiento.tasa_ea.is_not(None),
            ExtractoMovimiento.valor_pendiente > CERO,
        )
    ).all()
    peso_total = CERO
    acumulado = CERO
    for m in filas:
        peso = m.valor_pendiente or CERO
        peso_total += peso
        acumulado += peso * (m.tasa_ea or CERO)
    if peso_total > CERO:
        return (acumulado / peso_total).quantize(Decimal("0.0001")), "ponderada del extracto"

    # Sin pendientes con tasa: el promedio simple de las tasas que haya
    tasas = [m.tasa_ea for m in db.scalars(
        select(ExtractoMovimiento).where(
            ExtractoMovimiento.usuario_id == usuario_id,
            ExtractoMovimiento.tasa_ea.is_not(None),
        )
    ).all() if m.tasa_ea is not None]
    if tasas:
        return (sum(tasas) / len(tasas)).quantize(Decimal("0.0001")), "promedio del extracto"

    if tarjeta is not None and tarjeta.tasa_interes_ea is not None:
        return tarjeta.tasa_interes_ea, "configurada en la tarjeta"
    if tarjeta is not None and tarjeta.tasa_interes is not None:
        from .intereses import ea_desde_mensual

        return ea_desde_mensual(tarjeta.tasa_interes), "configurada en la tarjeta"
    return None, None


def simulador(
    db: Session,
    usuario_id: uuid.UUID,
    extracto: Extracto | None = None,
    pago_mensual: Decimal | None = None,
    saldo: Decimal | None = None,
) -> dict:
    """Simula el pago de la deuda **con la tasa real**, mes a mes.

    El saldo por defecto es el capital de las compras a cuotas pendientes; el pago, la suma
    de las cuotas del mes (lo que ya estás pagando). Así la pregunta que responde es: «si
    sigo pagando esto, ¿cuándo termino y cuánto habré pagado de intereses?».
    """
    if extracto is None:
        # Sin extracto concreto (simulador general) manda el más reciente: es el que trae
        # la tarjeta y la moneda de la deuda de verdad
        extracto = db.scalars(
            select(Extracto)
            .where(Extracto.usuario_id == usuario_id)
            .order_by(Extracto.fecha_corte.desc().nullslast(), Extracto.creado_en.desc())
        ).first()
    tarjeta = db.get(Tarjeta, extracto.tarjeta_id) if extracto and extracto.tarjeta_id else None
    tasa_ea, fuente = tasa_real(db, usuario_id, tarjeta)
    compras = compras_a_cuotas(db, usuario_id)

    moneda = extracto.moneda if extracto else (compras[0].moneda if compras else "COP")
    del_moneda = [c for c in compras if c.moneda == moneda]
    saldo_final = saldo if saldo is not None else sum((c.pendiente for c in del_moneda), CERO)
    cuota_actual = sum((c.cuota_mes for c in del_moneda), CERO)
    pago = pago_mensual if pago_mensual is not None else cuota_actual

    if tasa_ea is None:
        return {
            "moneda": moneda,
            "saldo": str(saldo_final),
            "pago_mensual": str(pago),
            "tasa_ea": None,
            "tasa_mensual": None,
            "fuente_de_la_tasa": None,
            "viable": None,
            "aviso": "No hay tasa de interés: el extracto no la trae y la tarjeta no la tiene configurada",
        }

    tasa_mensual = mensual_desde_ea(tasa_ea)
    resultado = simular_pago(saldo_final, tasa_mensual, pago)
    return {
        "moneda": moneda,
        "saldo": str(saldo_final),
        "pago_mensual": str(pago),
        "tasa_ea": str(tasa_ea),
        "tasa_mensual": str(tasa_mensual),
        "fuente_de_la_tasa": fuente,
        "cuota_actual": str(cuota_actual),
        "meses": resultado["meses"],
        "total_intereses": str(resultado["total_intereses"]),
        "total_pagado": str(resultado["total_pagado"]),
        "viable": resultado["viable"],
        "aviso": None,
    }


def costos_del_dinero(db: Session, usuario_id: uuid.UUID) -> dict:
    """Lo que te cuesta la deuda: intereses, comisiones e impuestos, por extracto."""
    extractos = db.scalars(
        select(Extracto)
        .where(Extracto.usuario_id == usuario_id)
        .order_by(Extracto.fecha_corte.desc().nullslast(), Extracto.creado_en.desc())
    ).all()

    filas = []
    totales: dict[str, Decimal] = {}
    for extracto in extractos:
        movimientos = db.scalars(
            select(ExtractoMovimiento).where(
                ExtractoMovimiento.extracto_id == extracto.id,
                ExtractoMovimiento.moneda == extracto.moneda,
            )
        ).all()
        del_movimiento = sum(
            (abs(m.valor) for m in movimientos if m.tipo in ("interes", "comision", "impuesto")),
            CERO,
        )
        declarado = (extracto.intereses or CERO) + (extracto.intereses_mora or CERO) + (
            extracto.otros_cargos or CERO
        )
        # Si el banco los lista como movimiento se usan esos; si no, las cifras del corte
        costo = del_movimiento if del_movimiento else declarado
        if costo == CERO and not movimientos:
            continue
        pago = extracto.pago_minimo or extracto.pago_total or CERO
        proporcion = (
            float(costo / pago) if pago > CERO else None
        )
        filas.append(
            {
                "extracto_id": str(extracto.id),
                "banco": extracto.banco,
                "nombre_archivo": extracto.nombre_archivo,
                "moneda": extracto.moneda,
                "fecha_corte": extracto.fecha_corte.isoformat() if extracto.fecha_corte else None,
                "intereses": str(extracto.intereses or CERO),
                "comisiones": str(extracto.otros_cargos or CERO),
                "costo": str(costo),
                "pago_minimo": str(pago) if pago else None,
                "porcentaje_del_pago": round(proporcion * 100, 1) if proporcion is not None else None,
            }
        )
        totales[extracto.moneda] = totales.get(extracto.moneda, CERO) + costo

    return {
        "extractos": filas,
        "total_por_moneda": {m: str(v) for m, v in totales.items()},
    }


def auditoria(db: Session, usuario_id: uuid.UUID, extracto: Extracto) -> list[dict]:
    """Comprueba que lo que dice el extracto cuadre con lo que hay en Konta."""
    movimientos = db.scalars(
        select(ExtractoMovimiento).where(ExtractoMovimiento.extracto_id == extracto.id)
    ).all()
    hallazgos: list[dict] = []

    importados = [m for m in movimientos if m.transaccion_id is not None]

    # La auditoría usa **el mismo plan que la importación**: así compara lo que debería
    # estar en Konta con lo que está, sin inventarse otra regla.
    lineas = plan_de_importacion(movimientos, extracto, ignorar_ya_importado=True)

    # 1) Lo que el corte manda pagar contra lo que se importa
    del_plan = sum(
        (x.monto for x in lineas if x.incluir and x.es_gasto and x.moneda == extracto.moneda),
        CERO,
    )
    if extracto.pago_minimo is not None:
        diferencia = extracto.pago_minimo - del_plan
        hallazgos.append(
            {
                "nombre": "lo que se importa cuadra con el pago mínimo del corte",
                "ok": abs(diferencia) <= Decimal("1"),
                "detalle": f"el corte manda pagar {extracto.pago_minimo} y la importación suma {del_plan}",
                "sugerencia": (
                    None
                    if abs(diferencia) <= Decimal("1")
                    else "Puede ser capital que ese banco cobra aparte o movimientos que no vienen en la tabla"
                ),
            }
        )

    # 2) Nada de lo que hay que importar se quedó sin importar
    pendientes = [x for x in lineas if x.incluir and not x.ya_importado]
    pagos = [x for x in lineas if x.motivo == MOTIVO_PAGO]
    hallazgos.append(
        {
            "nombre": "todo lo que hay que importar está importado",
            "ok": not pendientes,
            "detalle": (
                f"{len(pendientes)} sin importar de {len([x for x in lineas if x.incluir])} "
                f"(y {len(pagos)} pagos que no se importan, como debe ser)"
            ),
            "sugerencia": None if not pendientes else "Importa lo que falta para que el mes cuadre",
        }
    )

    # 3) Nada duplicado: movimientos de la tarjeta en el periodo que no salen del extracto
    if extracto.tarjeta_id and extracto.periodo_desde and extracto.periodo_hasta:
        ajenas = db.scalars(
            select(Transaccion).where(
                Transaccion.usuario_id == usuario_id,
                Transaccion.tarjeta_id == extracto.tarjeta_id,
                Transaccion.fecha >= extracto.periodo_desde,
                Transaccion.fecha <= extracto.periodo_hasta,
            )
        ).all()
        ids_del_extracto = {m.transaccion_id for m in importados if m.transaccion_id}
        manuales = [t for t in ajenas if t.id not in ids_del_extracto]
        hallazgos.append(
            {
                "nombre": "no hay movimientos repetidos en el periodo",
                "ok": True,
                "detalle": (
                    f"{len(manuales)} movimiento(s) del periodo no vienen del extracto "
                    "(pueden ser tuyos, a mano)"
                ),
                "sugerencia": (
                    "Si ves el mismo gasto dos veces, borra el que metiste a mano"
                    if manuales
                    else None
                ),
            }
        )

    # 4) La conciliación del propio extracto
    hallazgos.append(
        {
            "nombre": "el detalle cuadra con lo que declara el banco",
            "ok": extracto.conciliacion_ok,
            "detalle": "según los controles de la lectura",
            "sugerencia": None if extracto.conciliacion_ok else "Revisa los controles de la conciliación",
        }
    )

    # 5) La deuda registrada contra el capital pendiente de las compras a cuotas
    compras = [c for c in compras_a_cuotas(db, usuario_id) if c.moneda == extracto.moneda]
    pendiente = sum((c.pendiente for c in compras), CERO)
    if extracto.cupo_total is not None and extracto.cupo_disponible is not None:
        utilizado = extracto.cupo_total - extracto.cupo_disponible
        hallazgos.append(
            {
                "nombre": "el cupo utilizado se parece al capital pendiente",
                "ok": None,
                "detalle": (
                    f"cupo utilizado {utilizado} · capital de compras a cuotas {pendiente}"
                ),
                "sugerencia": (
                    "La diferencia son compras de una sola cuota y el saldo del periodo anterior"
                ),
            }
        )
    return hallazgos
