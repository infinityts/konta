"""CRUD de transacciones (aislado por usuario).

Aquí viven también las reglas de las **transferencias** entre cuentas propias: no
son ingreso ni gasto, así que quedan fuera de los reportes, del flujo de caja y de
los presupuestos, y mueven el saldo de dos cuentas a la vez.

Una transferencia exige que las dos cuentas estén en la **misma moneda**: mover
entre monedas distintas necesita su propia tasa y un segundo importe
(`monto_destino`), que es una tarea aparte.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..crud_utils import get_owned
from ..deps import get_current_user, get_db
from ..models import Cuenta, Tarjeta, Transaccion, TipoTransaccion, Usuario
from ..schemas import TransaccionIn, TransaccionOut, TransaccionUpdate

router = APIRouter(prefix="/transacciones", tags=["transacciones"])

# Lo que una transferencia **no** puede llevar: no tiene categoría (no es un gasto
# que se clasifique), ni tarjeta (no es un consumo), ni suscripción ni etiqueta.
CAMPOS_PROHIBIDOS = ("categoria_id", "tarjeta_id", "suscripcion_id", "etiqueta_id")


def _validar(datos: dict) -> None:
    """Coherencia del movimiento resultante (sirve para crear y para editar)."""
    es_transferencia = datos.get("tipo") == TipoTransaccion.TRANSFERENCIA

    if not es_transferencia:
        if datos.get("cuenta_destino_id") is not None:
            raise HTTPException(
                status_code=422,
                detail="Solo una transferencia puede tener cuenta de destino",
            )
        return

    if not datos.get("cuenta_id") or not datos.get("cuenta_destino_id"):
        raise HTTPException(
            status_code=422,
            detail="Una transferencia necesita la cuenta de origen y la de destino",
        )
    if datos["cuenta_id"] == datos["cuenta_destino_id"]:
        raise HTTPException(
            status_code=422, detail="El origen y el destino no pueden ser la misma cuenta"
        )
    for campo in CAMPOS_PROHIBIDOS:
        if datos.get(campo) is not None:
            raise HTTPException(
                status_code=422,
                detail=f"Una transferencia no lleva {campo}: no es un gasto que se clasifique",
            )


def _validar_cuentas(db: Session, user: Usuario, datos: dict) -> None:
    """Las referencias deben ser del usuario y las cuentas compartir moneda."""
    origen = destino = None
    if datos.get("cuenta_id") is not None:
        origen = get_owned(db, Cuenta, datos["cuenta_id"], user.id)
    if datos.get("cuenta_destino_id") is not None:
        destino = get_owned(db, Cuenta, datos["cuenta_destino_id"], user.id)
    if datos.get("tarjeta_id") is not None:
        get_owned(db, Tarjeta, datos["tarjeta_id"], user.id)
    if origen is not None and destino is not None and origen.moneda != destino.moneda:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Las cuentas están en monedas distintas ({origen.moneda} y {destino.moneda}): "
                "una transferencia entre monedas necesita su propia tasa y todavía no existe"
            ),
        )


@router.get("", response_model=list[TransaccionOut])
def listar(db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    return db.scalars(
        select(Transaccion)
        .where(Transaccion.usuario_id == user.id)
        .order_by(Transaccion.fecha.desc())
    ).all()


@router.post("", response_model=TransaccionOut, status_code=201)
def crear(data: TransaccionIn, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    datos = data.model_dump()
    _validar(datos)
    _validar_cuentas(db, user, datos)
    obj = Transaccion(usuario_id=user.id, **datos)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.get("/{id}", response_model=TransaccionOut)
def obtener(id: uuid.UUID, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    return get_owned(db, Transaccion, id, user.id)


@router.patch("/{id}", response_model=TransaccionOut)
def actualizar(id: uuid.UUID, data: TransaccionUpdate, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    obj = get_owned(db, Transaccion, id, user.id)
    campos = data.model_dump(exclude_unset=True)

    # Se valida el estado **resultante**, no solo lo que llega: al convertir un
    # movimiento en transferencia hay que mirar también lo que ya tenía guardado.
    resultante = {
        campo: getattr(obj, campo)
        for campo in (
            "tipo", "cuenta_id", "cuenta_destino_id",
            "categoria_id", "tarjeta_id", "suscripcion_id", "etiqueta_id",
        )
    }
    resultante.update(campos)
    _validar(resultante)
    _validar_cuentas(db, user, resultante)

    for campo, valor in campos.items():
        setattr(obj, campo, valor)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/{id}", status_code=204)
def eliminar(id: uuid.UUID, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    obj = get_owned(db, Transaccion, id, user.id)
    db.delete(obj)
    db.commit()
