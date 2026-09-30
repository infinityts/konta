"""Reglas de un movimiento, compartidas por la pantalla y por el asistente.

Vivían dentro del router de transacciones. Se movieron aquí para que las acciones que el
asistente propone y el usuario confirma pasen por **las mismas** validaciones que si se
registraran a mano: una sola puerta, no dos.
"""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.orm import Session

from .crud_utils import get_owned
from .models import (
    Categoria,
    Cuenta,
    Etiqueta,
    IngresoRecurrente,
    Poliza,
    Suscripcion,
    Tarjeta,
    TipoTarjeta,
    TipoTransaccion,
    Usuario,
)

# Campos que no se pueden tocar al crear un movimiento desde una recurrencia
CAMPOS_PROHIBIDOS = ("categoria_id", "suscripcion_id", "etiqueta_id")


def validar(datos: dict) -> None:
    """Coherencia del movimiento resultante (sirve para crear y para editar)."""
    es_transferencia = datos.get("tipo") == TipoTransaccion.TRANSFERENCIA

    if not es_transferencia:
        if datos.get("cuenta_destino_id") is not None:
            raise HTTPException(
                status_code=422,
                detail="Solo una transferencia puede tener cuenta de destino",
            )
        return

    if not datos.get("cuenta_id"):
        raise HTTPException(
            status_code=422, detail="Una transferencia necesita la cuenta de origen"
        )
    # El destino es otra cuenta (mover dinero) **o** una tarjeta de crédito (pagar su
    # deuda): exactamente uno de los dos, nunca los dos ni ninguno.
    destinos = [
        d for d in (datos.get("cuenta_destino_id"), datos.get("tarjeta_id")) if d is not None
    ]
    if len(destinos) != 1:
        raise HTTPException(
            status_code=422,
            detail=(
                "Una transferencia necesita **un** destino: otra cuenta o una tarjeta "
                "de crédito (pago de la deuda)"
            ),
        )
    if datos.get("cuenta_destino_id") is not None and datos["cuenta_id"] == datos["cuenta_destino_id"]:
        raise HTTPException(
            status_code=422, detail="El origen y el destino no pueden ser la misma cuenta"
        )
    for campo in CAMPOS_PROHIBIDOS:
        if datos.get(campo) is not None:
            raise HTTPException(
                status_code=422,
                detail=f"Una transferencia no lleva {campo}: no es un gasto que se clasifique",
            )

def validar_referencias(db: Session, user: Usuario, datos: dict) -> None:
    """Todas las referencias deben ser del usuario.

    Faltaba: se podía crear un movimiento apuntando a la **categoría o etiqueta de
    otro usuario** (el movimiento era tuyo, pero el reporte mostraba su nombre).
    """
    for campo, modelo in (
        ("categoria_id", Categoria),
        ("etiqueta_id", Etiqueta),
        ("tarjeta_id", Tarjeta),
        ("suscripcion_id", Suscripcion),
        ("ingreso_recurrente_id", IngresoRecurrente),
        ("poliza_id", Poliza),
    ):
        valor = datos.get(campo)
        if valor is not None:
            get_owned(db, modelo, valor, user.id)

def validar_cuentas(db: Session, user: Usuario, datos: dict) -> None:
    """Las cuentas deben ser del usuario y compartir moneda."""
    origen = destino = None
    if datos.get("cuenta_id") is not None:
        origen = get_owned(db, Cuenta, datos["cuenta_id"], user.id)
    if datos.get("cuenta_destino_id") is not None:
        destino = get_owned(db, Cuenta, datos["cuenta_destino_id"], user.id)

    # El destino también puede ser una tarjeta de crédito (pagar su deuda)
    tarjeta = None
    if datos.get("tarjeta_id") is not None:
        tarjeta = get_owned(db, Tarjeta, datos["tarjeta_id"], user.id)
        if (
            datos.get("tipo") == TipoTransaccion.TRANSFERENCIA
            and tarjeta.tipo != TipoTarjeta.CREDITO
        ):
            raise HTTPException(
                status_code=422,
                detail=(
                    f"«{tarjeta.nombre}» es de débito: su saldo es el de la cuenta "
                    "asociada, no una deuda que se pague con una transferencia"
                ),
            )
    if origen is not None and tarjeta is not None and origen.moneda != tarjeta.moneda:
        raise HTTPException(
            status_code=422,
            detail=(
                f"La cuenta está en {origen.moneda} y la tarjeta en {tarjeta.moneda}: "
                "un pago entre monedas necesita su propia tasa y todavía no existe"
            ),
        )
    if origen is not None and destino is not None and origen.moneda != destino.moneda:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Las cuentas están en monedas distintas ({origen.moneda} y {destino.moneda}): "
                "una transferencia entre monedas necesita su propia tasa y todavía no existe"
            ),
        )
