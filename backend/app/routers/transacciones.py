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
from ..models import (
    Categoria,
    Cuenta,
    EstadoSuscripcion,
    Etiqueta,
    IngresoRecurrente,
    Periodicidad,
    PeriodicidadIngreso,
    Poliza,
    Suscripcion,
    Tarjeta,
    TipoTarjeta,
    TipoTransaccion,
    Transaccion,
    Usuario,
)
from ..recurrencia import siguiente_ocurrencia, siguiente_pago
from ..schemas import TransaccionIn, TransaccionOut, TransaccionUpdate

router = APIRouter(prefix="/transacciones", tags=["transacciones"])

# Periodicidades válidas según el tipo de movimiento (los ENUM no son iguales)
PERIODICIDAD_GASTO = {p.value: p for p in Periodicidad}
PERIODICIDAD_INGRESO = {p.value: p for p in PeriodicidadIngreso}

# Lo que una transferencia **no** puede llevar: no tiene categoría (no es un gasto
# que se clasifique), ni suscripción ni etiqueta.
CAMPOS_PROHIBIDOS = ("categoria_id", "suscripcion_id", "etiqueta_id")


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


def _validar_referencias(db: Session, user: Usuario, datos: dict) -> None:
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


def _validar_cuentas(db: Session, user: Usuario, datos: dict) -> None:
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


@router.get("", response_model=list[TransaccionOut])
def listar(db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    return db.scalars(
        select(Transaccion)
        .where(Transaccion.usuario_id == user.id)
        .order_by(Transaccion.fecha.desc())
    ).all()


def _crear_compromiso(db: Session, user: Usuario, datos: dict, periodicidad: str) -> dict:
    """Crea el compromiso recurrente y devuelve el enlace para la transacción.

    La transacción que se está creando es el pago de **este** periodo, así que el
    compromiso queda apuntando al **siguiente**: el job no duplica el de ahora.

    El día sale de la fecha del movimiento (día del mes o de la semana), y el
    nombre, el monto, la categoría, la etiqueta, la cuenta y la tarjeta se heredan
    del propio movimiento: no hay que teclear nada dos veces.
    """
    tipo = datos["tipo"]
    fecha = datos["fecha"]
    nombre = (datos.get("descripcion") or "").strip() or "Movimiento recurrente"

    if tipo == TipoTransaccion.TRANSFERENCIA:
        raise HTTPException(
            status_code=422,
            detail=(
                "Una transferencia no puede ser recurrente todavía: el compromiso "
                "tiene que saber de qué cuenta sale y a cuál entra en cada periodo"
            ),
        )

    if tipo == TipoTransaccion.GASTO:
        if periodicidad not in PERIODICIDAD_GASTO:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"«{periodicidad}» no vale para un gasto recurrente; usa una de "
                    f"{', '.join(PERIODICIDAD_GASTO)}"
                ),
            )
        per = PERIODICIDAD_GASTO[periodicidad]
        compromiso = Suscripcion(
            usuario_id=user.id,
            nombre=nombre,
            monto=datos["monto"],
            moneda=datos["moneda"],
            periodicidad=per,
            fecha_inicio=fecha,
            proximo_pago=siguiente_pago(per, fecha),
            categoria_id=datos.get("categoria_id"),
            etiqueta_id=datos.get("etiqueta_id"),
            tarjeta_id=datos.get("tarjeta_id"),
            cuenta_id=datos.get("cuenta_id"),
            estado=EstadoSuscripcion.ACTIVA,
            notas="Creado desde una transacción",
        )
        db.add(compromiso)
        db.flush()
        return {"suscripcion_id": compromiso.id}

    if periodicidad not in PERIODICIDAD_INGRESO:
        raise HTTPException(
            status_code=422,
            detail=(
                f"«{periodicidad}» no vale para un ingreso recurrente; usa una de "
                f"{', '.join(PERIODICIDAD_INGRESO)}"
            ),
        )
    per_i = PERIODICIDAD_INGRESO[periodicidad]
    dia = None
    if per_i == PeriodicidadIngreso.SEMANAL:
        dia = fecha.weekday()
    elif per_i == PeriodicidadIngreso.MENSUAL:
        dia = fecha.day
    compromiso = IngresoRecurrente(
        usuario_id=user.id,
        nombre=nombre,
        monto=datos["monto"],
        moneda=datos["moneda"],
        periodicidad=per_i,
        dia=dia,
        proxima_ejecucion=siguiente_ocurrencia(per_i, dia, fecha),
        categoria_id=datos.get("categoria_id"),
        cuenta_id=datos.get("cuenta_id"),
    )
    db.add(compromiso)
    db.flush()
    return {"ingreso_recurrente_id": compromiso.id}


@router.post("", response_model=TransaccionOut, status_code=201)
def crear(data: TransaccionIn, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    datos = data.model_dump()
    recurrencia = datos.pop("recurrencia", None)
    _validar(datos)
    _validar_cuentas(db, user, datos)
    _validar_referencias(db, user, datos)

    if recurrencia is not None:
        # Atómico: el movimiento y el compromiso se guardan juntos o no se guarda nada
        datos.update(_crear_compromiso(db, user, datos, recurrencia["periodicidad"]))

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
            "tipo", "cuenta_id", "cuenta_destino_id", "categoria_id", "tarjeta_id",
            "suscripcion_id", "ingreso_recurrente_id", "etiqueta_id",
        )
    }
    resultante.update(campos)
    _validar(resultante)
    _validar_cuentas(db, user, resultante)
    _validar_referencias(db, user, resultante)

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
