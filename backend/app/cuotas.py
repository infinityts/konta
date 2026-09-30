"""Cuotas y consumo: lo que cada plan incluye y lo que se ha gastado.

Vender lecturas de factura con IA sin regalar dinero necesita tres cosas: un **límite** por
plan, un **medidor** de lo usado en el mes y un **saldo** de lecturas compradas aparte. Aquí
están las tres.

El coste real (tokens y dólares) se guarda además del conteo, porque lo que decide si un plan
deja ganancia no es cuántas lecturas hizo el usuario sino cuánto costaron.
"""

from __future__ import annotations

from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import ConsumoIa, Plan, Usuario
from .recurrencia import hoy

# Recursos que se pueden agotar
LECTURA_IA = "lectura_ia"
CONSULTA_ASISTENTE = "consulta_asistente"

PLAN_POR_DEFECTO = "basico"


def periodo_actual() -> str:
    """El mes del usuario, en su zona (el mes que él vive, no el de UTC)."""
    return hoy().strftime("%Y-%m")


def plan_de(db: Session, usuario: Usuario) -> Plan | None:
    return db.get(Plan, usuario.plan_codigo or PLAN_POR_DEFECTO)


def consumo_de(db: Session, usuario: Usuario, periodo: str | None = None) -> ConsumoIa:
    """El consumo del mes; si no existe, se crea vacío (así el resto del código no comprueba)."""
    periodo = periodo or periodo_actual()
    consumo = db.scalar(
        select(ConsumoIa).where(
            ConsumoIa.usuario_id == usuario.id, ConsumoIa.periodo == periodo
        )
    )
    if consumo is None:
        consumo = ConsumoIa(usuario_id=usuario.id, periodo=periodo)
        db.add(consumo)
        db.flush()
    return consumo


def _limite(db: Session, usuario: Usuario, recurso: str) -> int:
    plan = plan_de(db, usuario)
    if plan is None:
        return 0
    return plan.lecturas_ia if recurso == LECTURA_IA else plan.consultas_asistente


def resumen(db: Session, usuario: Usuario) -> dict:
    """Lo que le queda este mes: incluido, comprado aparte y gastado."""
    consumo = consumo_de(db, usuario)
    plan = plan_de(db, usuario)
    lecturas_limite = _limite(db, usuario, LECTURA_IA)
    consultas_limite = _limite(db, usuario, CONSULTA_ASISTENTE)
    extra = usuario.lecturas_extra or 0
    # Almacenamiento (importa aquí dentro para no crear un ciclo entre módulos)
    from .archivos import resumen as resumen_almacen

    almacen_resumen = resumen_almacen(db, usuario)
    # En qué plan está y hasta cuándo (importa aquí dentro para no crear un ciclo)
    from .pagos import estado_del_plan

    plan_estado = estado_del_plan(usuario)
    return {
        "periodo": consumo.periodo,
        "plan": plan.codigo if plan else None,
        "plan_nombre": plan.nombre if plan else None,
        "precio_mes": float(plan.precio_mes) if plan else 0.0,
        "lecturas": {
            "incluidas": lecturas_limite,
            "usadas": consumo.lecturas,
            # El saldo comprado se gasta **después** de lo incluido
            "extra": extra,
            "restantes": max(0, lecturas_limite - consumo.lecturas) + extra,
        },
        "consultas": {
            "incluidas": consultas_limite,
            "usadas": consumo.consultas,
            "restantes": max(0, consultas_limite - consumo.consultas),
        },
        "tokens_entrada": consumo.tokens_entrada,
        "tokens_salida": consumo.tokens_salida,
        "costo_usd": float(consumo.costo_usd),
        "plan_hasta": plan_estado["hasta"],
        "dias_de_plan": plan_estado["dias"],
        "plan_por_vencer": plan_estado["por_vencer"],
        **almacen_resumen,
    }


def agotado(recurso: str, resumen_actual: dict) -> HTTPException:
    """El error se explica y dice qué hacer: no basta con un 402 pelado."""
    if recurso == LECTURA_IA:
        detalle = (
            "Se acabaron las lecturas con IA de este mes "
            f"({resumen_actual['lecturas']['incluidas']} en tu plan). "
            "Puedes comprar lecturas sueltas o subir de plan; mientras tanto, la lectura "
            "normal de Konta sigue funcionando."
        )
    else:
        detalle = (
            "Se acabaron las consultas al asistente de este mes "
            f"({resumen_actual['consultas']['incluidas']} en tu plan). "
            "Puedes subir de plan para seguir preguntando."
        )
    return HTTPException(status_code=402, detail=detalle)


def consumir(db: Session, usuario: Usuario, recurso: str, unidades: int = 1) -> ConsumoIa:
    """Gasta una unidad del recurso o explica por qué no se puede.

    Se comprueba **antes** de llamar al proveedor de IA: si no hay cupo, no se gasta un token.
    """
    actual = resumen(db, usuario)
    if recurso == LECTURA_IA:
        if actual["lecturas"]["restantes"] < unidades:
            raise agotado(recurso, actual)
        consumo = consumo_de(db, usuario)
        consumo.lecturas += unidades
    else:
        if actual["consultas"]["restantes"] < unidades:
            raise agotado(recurso, actual)
        consumo = consumo_de(db, usuario)
        consumo.consultas += unidades

    # El saldo comprado se descuenta solo cuando lo incluido ya se agotó
    if recurso == LECTURA_IA and consumo.lecturas > actual["lecturas"]["incluidas"]:
        usuario.lecturas_extra = max(0, (usuario.lecturas_extra or 0) - unidades)
    db.commit()
    db.refresh(consumo)
    return consumo


def registrar_gasto(
    db: Session,
    usuario: Usuario,
    tokens_entrada: int = 0,
    tokens_salida: int = 0,
    costo_usd: Decimal | float = 0,
) -> ConsumoIa:
    """Anota los tokens y el coste real que facturó el proveedor (para vigilar el margen)."""
    consumo = consumo_de(db, usuario)
    consumo.tokens_entrada += tokens_entrada
    consumo.tokens_salida += tokens_salida
    consumo.costo_usd = Decimal(str(consumo.costo_usd or 0)) + Decimal(str(costo_usd))
    db.commit()
    db.refresh(consumo)
    return consumo


def costo_de_lectura(
    tokens_entrada: int, tokens_salida: int, precio_entrada: float, precio_salida: float
) -> Decimal:
    """Lo que cuesta una lectura en dólares, con los precios por millón de tokens.

    Los precios se pasan desde fuera a propósito: cambian (y hay tarifas con y sin caché, y
    horas valle), así que la app no los lleva escritos en el código.
    """
    costo = (tokens_entrada / 1_000_000) * precio_entrada
    costo += (tokens_salida / 1_000_000) * precio_salida
    return Decimal(str(round(costo, 6)))
