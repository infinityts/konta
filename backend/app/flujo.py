"""Proyección de flujo de caja.

Proyecta los próximos N meses a partir de:
- **Ingresos recurrentes** activos (diario/semanal/mensual).
- **Cobros fijos** activos: suscripciones **y pólizas de seguro**
  (semanal/mensual/trimestral/semestral/anual).
- **Gasto variable** = promedio mensual de los gastos que no vienen de una
  suscripción ni de una póliza, de los últimos meses completos.

**Todo se expresa en COP.** Cada importe se convierte con la tasa registrada; si
no hay tasa para una moneda, ese cobro **no se suma** y la moneda se informa en
`sin_tasa` (antes se sumaban los números en crudo: USD 10 contaba como $10).
"""

from __future__ import annotations

import calendar
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import (
    EstadoSuscripcion,
    IngresoRecurrente,
    Periodicidad,
    PeriodicidadIngreso,
    Poliza,
    Suscripcion,
    TipoTransaccion,
    Transaccion,
)
from .recurrencia import hoy
from .tasas import convertir

CERO = Decimal("0.00")


def _sumar_mes(fecha: date, n: int) -> date:
    y = fecha.year + (fecha.month - 1 + n) // 12
    m = (fecha.month - 1 + n) % 12 + 1
    return date(y, m, min(fecha.day, calendar.monthrange(y, m)[1]))


def _fin_de_mes(fecha: date) -> date:
    return date(fecha.year, fecha.month, calendar.monthrange(fecha.year, fecha.month)[1])


def _meses_del_rango(inicio: date, fin: date) -> list[str]:
    meses, actual = [], inicio
    while actual <= fin:
        meses.append(f"{actual.year:04d}-{actual.month:02d}")
        actual = _sumar_mes(actual, 1)
    return meses


def _ocurrencias_ingreso(ing: IngresoRecurrente, inicio: date, fin: date) -> list[date]:
    salida: list[date] = []
    if ing.periodicidad == PeriodicidadIngreso.DIARIO:
        cursor = max(ing.proxima_ejecucion, inicio)
        while cursor <= fin and len(salida) < 400:
            salida.append(cursor)
            cursor += timedelta(days=1)
    elif ing.periodicidad == PeriodicidadIngreso.SEMANAL:
        cursor = max(ing.proxima_ejecucion, inicio)
        cursor += timedelta(days=((ing.dia or 0) - cursor.weekday()) % 7)
        while cursor <= fin and len(salida) < 400:
            salida.append(cursor)
            cursor += timedelta(days=7)
    else:  # mensual
        cursor = ing.proxima_ejecucion
        guarda = 0
        while cursor < inicio and guarda < 400:
            cursor = _sumar_mes(cursor, 1)
            guarda += 1
        while cursor <= fin and guarda < 400:
            salida.append(cursor)
            cursor = _sumar_mes(cursor, 1)
            guarda += 1
    return salida


def _ocurrencias_cobro(cobro, inicio: date, fin: date) -> list[date]:
    """Fechas de cobro de una suscripción o póliza dentro del rango.

    Ojo con `SEMESTRAL`: sin su entrada en el mapa caía al valor por defecto (1
    mes) y una prima semestral se proyectaba como si se pagara cada mes.
    """
    cursor = cobro.proximo_pago or cobro.fecha_inicio or inicio
    paso = {
        Periodicidad.SEMANAL: 0,
        Periodicidad.MENSUAL: 1,
        Periodicidad.TRIMESTRAL: 3,
        Periodicidad.SEMESTRAL: 6,
        Periodicidad.ANUAL: 12,
    }.get(cobro.periodicidad, 1)

    salida: list[date] = []
    guarda = 0
    while cursor < inicio and guarda < 400:
        cursor = cursor + timedelta(days=7) if paso == 0 else _sumar_mes(cursor, paso)
        guarda += 1
    while cursor <= fin and guarda < 400:
        salida.append(cursor)
        cursor = cursor + timedelta(days=7) if paso == 0 else _sumar_mes(cursor, paso)
        guarda += 1
    return salida


def _en_cop(db: Session, monto, moneda: str, sin_tasa: list[str]) -> Decimal | None:
    """Monto en COP. `None` si no hay tasa: se anota la moneda y no se suma."""
    valor = Decimal(str(monto))
    if moneda == "COP":
        return valor
    convertido = convertir(db, moneda, "COP", valor)
    if convertido is None:
        if moneda not in sin_tasa:
            sin_tasa.append(moneda)
        return None
    return convertido


def gasto_variable_promedio(db: Session, usuario_id, meses: int = 3) -> Decimal:
    """Promedio mensual de los gastos que **no** son un cobro fijo.

    Se excluyen los que generó una suscripción **y los que generó una póliza**:
    esos ya entran como gasto fijo en su mes, y contarlos aquí los contaría dos
    veces (la póliza es más nueva que este filtro).
    """
    hoy_ = hoy()
    primer_mes_actual = date(hoy_.year, hoy_.month, 1)
    desde = _sumar_mes(primer_mes_actual, -meses)
    hasta = primer_mes_actual - timedelta(days=1)

    total = db.scalar(
        select(func.coalesce(func.sum(Transaccion.monto), 0)).where(
            Transaccion.usuario_id == usuario_id,
            Transaccion.tipo == TipoTransaccion.GASTO,
            Transaccion.suscripcion_id.is_(None),
            Transaccion.poliza_id.is_(None),
            Transaccion.fecha >= desde,
            Transaccion.fecha <= hasta,
        )
    )
    return (Decimal(total) / meses).quantize(Decimal("0.01")) if meses else CERO


def proyectar(db: Session, usuario_id, meses: int = 6) -> dict:
    hoy_ = hoy()
    inicio = date(hoy_.year, hoy_.month, 1)
    fin = _fin_de_mes(_sumar_mes(inicio, meses - 1))
    etiquetas = _meses_del_rango(inicio, fin)

    ingresos_rec = db.scalars(
        select(IngresoRecurrente).where(
            IngresoRecurrente.usuario_id == usuario_id,
            IngresoRecurrente.activa.is_(True),
        )
    ).all()
    suscripciones = db.scalars(
        select(Suscripcion).where(
            Suscripcion.usuario_id == usuario_id,
            Suscripcion.estado == EstadoSuscripcion.ACTIVA,
        )
    ).all()
    polizas = db.scalars(
        select(Poliza).where(
            Poliza.usuario_id == usuario_id,
            Poliza.estado == EstadoSuscripcion.ACTIVA,
        )
    ).all()

    ingresos_por_mes: dict[str, Decimal] = {m: CERO for m in etiquetas}
    fijos_por_mes: dict[str, Decimal] = {m: CERO for m in etiquetas}
    sin_tasa: list[str] = []

    for ing in ingresos_rec:
        valor = _en_cop(db, ing.monto, ing.moneda, sin_tasa)
        if valor is None:
            continue
        for fecha in _ocurrencias_ingreso(ing, inicio, fin):
            clave = f"{fecha.year:04d}-{fecha.month:02d}"
            if clave in ingresos_por_mes:
                ingresos_por_mes[clave] += valor

    cobros = [(s, s.monto) for s in suscripciones] + [(p, p.prima) for p in polizas]
    for cobro, monto in cobros:
        valor = _en_cop(db, monto, cobro.moneda, sin_tasa)
        if valor is None:
            continue
        for fecha in _ocurrencias_cobro(cobro, inicio, fin):
            clave = f"{fecha.year:04d}-{fecha.month:02d}"
            if clave in fijos_por_mes:
                fijos_por_mes[clave] += valor

    variable = gasto_variable_promedio(db, usuario_id)

    acumulado = CERO
    filas = []
    for mes in etiquetas:
        ingresos = ingresos_por_mes[mes]
        fijos = fijos_por_mes[mes]
        gastos = fijos + variable
        balance = ingresos - gastos
        acumulado += balance
        filas.append(
            {
                "mes": mes,
                "ingresos": float(ingresos),
                "gastos_fijos": float(fijos),
                "gastos_variables": float(variable),
                "gastos": float(gastos),
                "balance": float(balance),
                "acumulado": float(acumulado),
            }
        )

    return {
        "moneda": "COP",
        "sin_tasa": sin_tasa,
        "meses": filas,
        "gasto_variable_promedio": float(variable),
        "total_ingresos": float(sum(ingresos_por_mes.values())),
        "total_gastos": float(sum(fijos_por_mes.values()) + variable * len(etiquetas)),
        "balance_final": float(acumulado),
    }
