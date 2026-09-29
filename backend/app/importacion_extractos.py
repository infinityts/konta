"""Importar los movimientos de un extracto a Konta (Fase 2).

Las reglas salen de tus decisiones y de lo que enseñan los extractos reales:

- **La cuota del mes es el gasto.** Una compra a 24 cuotas no es un gasto de una vez:
  lo que se gasta este mes es la cuota. El capital que queda por pagar es deuda, no
  gasto (eso se ve en el «compromiso futuro», no en los reportes del mes).
- **Los ajustes no se importan.** En los extractos vienen en pareja (`AJUSTE PAGO MIN
  ALTO +772.653,02` y su reverso en negativo): suman cero, no es plata que se movió.
- **Solo el periodo.** Lo anterior al periodo es el capital de compras de meses atrás;
  importarlo volvería a contar un gasto que ya estaba contado el mes en que se hizo.
- **Los pagos tampoco son un gasto.** Pagar la deuda propia no es un gasto (mover dinero
  a pagar algo tuyo ya tiene su sitio: un pago de tarjeta). Si se importaran como gasto,
  la compra se contaría dos veces: al comprar y al pagar.
- **Nada se inventa.** Si una compra a cuotas no trae la cuota del mes, no se importa y
  se dice por qué, en vez de meter el valor completo (que inflaría el mes) o la mitad.

Este módulo es puro (no toca la base salvo en `ejecutar`), para poder previsualizar
exactamente lo mismo que se va a importar.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.orm import Session

from .models import (
    DeudaTarjeta,
    Extracto,
    ExtractoMovimiento,
    Tarjeta,
    TipoTransaccion,
    Transaccion,
)
from .recurrencia import hoy

CERO = Decimal("0")

# Por qué **no** se importa cada línea (se enseña tal cual en la previsualización)
MOTIVO_INFORMATIVO = (
    "es una compra de meses anteriores que se pagó de una vez: su valor ya se contó "
    "cuando la compraste"
)
MOTIVO_CUOTA_ANTERIOR = "es la cuota de este mes de una compra de meses anteriores"
MOTIVO_AJUSTE = "es un ajuste: suma y resta lo mismo, no movió plata"
MOTIVO_PAGO = "es un pago de tu deuda: pagar lo tuyo no es un gasto"
MOTIVO_TRANSFERENCIA = "es una transferencia entre tus cuentas: no es gasto ni ingreso"
MOTIVO_YA_IMPORTADO = "ya se importó antes"
MOTIVO_SIN_CUOTA = "es una compra a cuotas y el extracto no dice la cuota del mes"
MOTIVO_SIN_MONTO = "no tiene monto"


@dataclass
class LineaImportacion:
    """Qué va a pasar con un movimiento: se importa o no, y por qué."""

    movimiento_id: uuid.UUID | None
    fecha: str | None
    descripcion: str
    moneda: str
    # Monto que se va a registrar (la cuota del mes, no el valor de la compra)
    monto: Decimal
    valor_compra: Decimal
    tipo: str
    incluir: bool
    motivo: str | None
    ya_importado: bool
    categoria_id: uuid.UUID | None
    etiqueta_id: uuid.UUID | None
    es_gasto: bool = True
    # La cuota de una compra de meses anteriores también se paga **este** mes
    de_meses_anteriores: bool = False
    # Línea que no viene de un movimiento sino de una cifra del corte (intereses del mes)
    sintetica: bool = False


def _monto_a_importar(
    m: ExtractoMovimiento, incluir_cuotas_anteriores: bool = True
) -> tuple[Decimal | None, str | None]:
    """El monto del mes y, si no se puede, el motivo.

    Ojo con lo anterior al periodo: **su cuota del mes sí es un gasto de este mes** (es
    plata que sale ahora, y es lo que hace que el pago mínimo cuadre: en el extracto de
    Davivienda, 84.877,19 de las compras del periodo + 170.575,21 de las anteriores +
    97.624,49 de intereses = 353.076,89, el pago mínimo exacto). Lo que **no** se importa
    es el valor completo de una compra de meses anteriores: eso ya se contó cuando se
    compró.
    """
    if m.tipo == "ajuste":
        return None, MOTIVO_AJUSTE
    if m.tipo == "pago":
        return None, MOTIVO_PAGO
    if m.tipo == "transferencia":
        return None, MOTIVO_TRANSFERENCIA
    if m.transaccion_id is not None:
        return None, MOTIVO_YA_IMPORTADO

    # Compra a cuotas: lo del mes es la cuota, no el valor de la compra. Da igual si es
    # de este periodo o de meses anteriores: este mes se paga esa cuota.
    if m.cuotas_total and m.cuotas_total > 1:
        if m.es_informativo and not incluir_cuotas_anteriores:
            return None, MOTIVO_CUOTA_ANTERIOR
        if m.cuota_mes is None or m.cuota_mes == CERO:
            return None, MOTIVO_SIN_CUOTA
        return abs(m.cuota_mes), None

    if m.es_informativo:
        return None, MOTIVO_INFORMATIVO

    if m.valor == CERO:
        return None, MOTIVO_SIN_MONTO

    # Compra a cuotas: lo del mes es la cuota, no el valor de la compra
    if m.cuotas_total and m.cuotas_total > 1:
        if m.cuota_mes is None or m.cuota_mes == CERO:
            return None, MOTIVO_SIN_CUOTA
        return abs(m.cuota_mes), None

    return abs(m.valor), None


def _es_ingreso(m: ExtractoMovimiento) -> bool:
    """En una **cuenta**, una nómina entra; en una tarjeta todo lo que suma es compra."""
    return m.tipo == "nomina" or (m.tipo == "otro" and m.valor < CERO)


def _descripcion(m: ExtractoMovimiento) -> str:
    base = (m.descripcion or "Movimiento del extracto").strip()
    if m.cuotas_total and m.cuotas_total > 1 and m.cuotas_n:
        base = f"{base} (cuota {m.cuotas_n}/{m.cuotas_total})"
    return base[:255]


def plan_de_importacion(
    movimientos: list[ExtractoMovimiento],
    extracto: Extracto | None = None,
    incluir_cuotas_anteriores: bool = True,
) -> list[LineaImportacion]:
    """Qué se importaría y qué no, sin tocar nada. Es lo mismo que ejecuta la importación.

    Si se le pasa el extracto, añade las cifras que el corte declara y que **no** vienen
    como movimiento (los intereses del mes, por ejemplo): sin ellas el mes no cuadra con
    lo que se paga.
    """
    lineas: list[LineaImportacion] = []
    for m in movimientos:
        monto, motivo = _monto_a_importar(m, incluir_cuotas_anteriores)
        lineas.append(
            LineaImportacion(
                movimiento_id=m.id,
                fecha=m.fecha.isoformat() if m.fecha else None,
                descripcion=_descripcion(m),
                moneda=m.moneda,
                monto=monto if monto is not None else CERO,
                valor_compra=abs(m.valor),
                tipo=m.tipo,
                incluir=monto is not None,
                motivo=motivo,
                ya_importado=m.transaccion_id is not None,
                categoria_id=m.categoria_id,
                etiqueta_id=m.etiqueta_id,
                es_gasto=not _es_ingreso(m),
                de_meses_anteriores=bool(m.es_informativo and monto is not None),
            )
        )

    if extracto is not None:
        lineas.extend(_lineas_del_corte(extracto, movimientos))
    return lineas


def _lineas_del_corte(
    extracto: Extracto, movimientos: list[ExtractoMovimiento]
) -> list[LineaImportacion]:
    """Las cifras del corte que no vienen como movimiento: intereses y otros cargos.

    El extracto de Davivienda declara 97.624,49 de intereses que **no** aparecen en su
    tabla de movimientos. Si no se importan, el mes no cuadra con el pago mínimo. Cuando
    el banco sí los lista (Amex), no se añade nada para no contarlos dos veces.
    """
    def ya_esta(tipos: tuple[str, ...]) -> bool:
        return any(m.tipo in tipos and m.valor != CERO for m in movimientos)

    lineas: list[LineaImportacion] = []
    declarado = [
        ("interes", extracto.intereses, "Intereses corrientes del corte"),
        ("interes", extracto.intereses_mora, "Intereses de mora del corte"),
        ("comision", extracto.otros_cargos, "Otros cargos del corte"),
    ]
    for tipo, monto, descripcion in declarado:
        if monto is None or monto == CERO:
            continue
        if ya_esta((tipo,) if tipo == "interes" else ("comision", "impuesto")):
            continue
        lineas.append(
            LineaImportacion(
                movimiento_id=None,
                fecha=extracto.fecha_corte.isoformat() if extracto.fecha_corte else None,
                descripcion=descripcion,
                moneda=extracto.moneda,
                monto=abs(monto),
                valor_compra=abs(monto),
                tipo=tipo,
                incluir=True,
                motivo="lo declara el corte y no viene como movimiento",
                ya_importado=False,
                categoria_id=None,
                etiqueta_id=None,
                sintetica=True,
            )
        )
    return lineas


def resumen_del_plan(lineas: list[LineaImportacion]) -> dict:
    """Cuántas se importan, cuántas no y por qué. Y los totales por moneda."""
    incluidas = [x for x in lineas if x.incluir]
    por_moneda: dict[str, Decimal] = {}
    ingresos: dict[str, Decimal] = {}
    for x in incluidas:
        destino = por_moneda if x.es_gasto else ingresos
        destino[x.moneda] = destino.get(x.moneda, CERO) + x.monto

    motivos: dict[str, int] = {}
    for x in lineas:
        if x.incluir or not x.motivo:
            continue
        motivos[x.motivo] = motivos.get(x.motivo, 0) + 1

    de_anteriores = sum(
        (x.monto for x in incluidas if x.de_meses_anteriores), CERO
    )
    return {
        "total": len(lineas),
        "se_importan": len(incluidas),
        "se_omiten": len(lineas) - len(incluidas),
        "gastos_por_moneda": {m: str(v) for m, v in por_moneda.items()},
        "ingresos_por_moneda": {m: str(v) for m, v in ingresos.items()},
        "motivos": motivos,
        "de_meses_anteriores": str(de_anteriores),
    }


def comparar_con_el_pago_minimo(
    resumen: dict, extracto: Extracto
) -> tuple[Decimal | None, str | None]:
    """¿Lo que se importa es lo que hay que pagar este mes?

    El **pago mínimo** del corte es la cifra con la que tiene que cuadrar el mes: las
    cuotas que te facturan (de compras nuevas y viejas) más intereses y comisiones. No
    siempre cuadra: hay bancos cuyo «pago mínimo» es un porcentaje del saldo y no la
    facturación del mes (Amex). Cuando no cuadra se dice, no se disimula.
    """
    if extracto.pago_minimo is None:
        return None, None
    importado = Decimal(resumen["gastos_por_moneda"].get(extracto.moneda, "0"))
    diferencia = extracto.pago_minimo - importado
    if abs(diferencia) <= Decimal("1"):
        return CERO, (
            "Lo que se importa coincide con el pago mínimo del corte: es exactamente lo que "
            "tienes que pagar este mes."
        )
    return diferencia, (
        f"El pago mínimo del corte es {extracto.pago_minimo} y se importan {importado}: "
        f"la diferencia ({diferencia}) puede ser capital que ese banco cobra aparte o "
        "movimientos que no vienen en la tabla. Revísalo antes de importar."
    )


def registrar_deuda_del_corte(
    db: Session, usuario_id: uuid.UUID, extracto: Extracto, tarjeta: Tarjeta | None
) -> DeudaTarjeta | None:
    """Registra el **cupo utilizado** del corte como deuda de la tarjeta.

    Decidiste registrar las dos cifras del corte: el **pago total** es la obligación de
    pagar (vive en el extracto e impulsa las alertas) y el **cupo utilizado** es la
    deuda. La deuda de una tarjeta es un **nivel** por moneda, y eso es exactamente lo
    que ya modela `DeudaTarjeta`, así que se registra ahí y todo lo demás (el total en
    COP, el simulador) sigue funcionando sin cambios.
    """
    if tarjeta is None or usuario_id is None:
        return None
    if extracto.cupo_total is None or extracto.cupo_disponible is None:
        return None
    utilizado = extracto.cupo_total - extracto.cupo_disponible
    if utilizado <= CERO:
        return None
    fecha = extracto.fecha_corte or extracto.periodo_hasta or hoy()
    deuda = DeudaTarjeta(
        usuario_id=usuario_id,
        tarjeta_id=tarjeta.id,
        moneda=extracto.moneda,
        monto=utilizado,
        fecha=fecha,
        notas=f"Cupo utilizado según el extracto del {fecha.isoformat()}",
    )
    db.add(deuda)
    return deuda


def ejecutar_importacion(
    db: Session,
    usuario_id: uuid.UUID,
    extracto: Extracto,
    movimientos: list[ExtractoMovimiento],
    cuenta_id: uuid.UUID | None = None,
    tarjeta_id: uuid.UUID | None = None,
    incluir_cuotas_anteriores: bool = True,
) -> dict:
    """Crea las transacciones de las líneas que se importan y las enlaza al extracto.

    Devuelve el resumen. Es **idempotente**: un movimiento ya importado no se vuelve a
    importar (y lo dice), así que pulsar dos veces no duplica nada.
    """
    lineas = plan_de_importacion(movimientos, extracto, incluir_cuotas_anteriores)
    por_id = {m.id: m for m in movimientos}
    creadas: list[Transaccion] = []

    for linea in lineas:
        if not linea.incluir:
            continue
        movimiento = por_id.get(linea.movimiento_id) if linea.movimiento_id else None
        if movimiento is None and not linea.sintetica:
            continue
        transaccion = Transaccion(
            usuario_id=usuario_id,
            tipo=TipoTransaccion.GASTO if linea.es_gasto else TipoTransaccion.INGRESO,
            monto=linea.monto,
            moneda=linea.moneda,
            fecha=(movimiento.fecha if movimiento is not None else None) or hoy(),
            descripcion=linea.descripcion,
            categoria_id=linea.categoria_id,
            etiqueta_id=linea.etiqueta_id,
            cuenta_id=cuenta_id,
            tarjeta_id=tarjeta_id,
        )
        db.add(transaccion)
        db.flush()
        if movimiento is not None:
            movimiento.transaccion_id = transaccion.id
        creadas.append(transaccion)

    resultado = resumen_del_plan(lineas)
    resultado["creadas"] = len(creadas)
    diferencia, nota = comparar_con_el_pago_minimo(resultado, extracto)
    resultado["pago_minimo"] = extracto.pago_minimo
    resultado["diferencia_pago_minimo"] = diferencia
    resultado["nota_pago_minimo"] = nota

    # La deuda del corte se registra solo cuando la importación hizo algo, para no
    # crear un nivel de deuda al abrir una previsualización
    tarjeta = db.get(Tarjeta, tarjeta_id) if tarjeta_id else None
    deuda = registrar_deuda_del_corte(db, usuario_id, extracto, tarjeta) if creadas else None
    resultado["deuda_registrada"] = str(deuda.monto) if deuda is not None else None
    return resultado
