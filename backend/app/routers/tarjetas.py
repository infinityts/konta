"""Tarjetas: deuda por moneda (del extracto) y simulador de intereses."""

from __future__ import annotations

import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..crud_utils import get_owned
from ..deps import get_current_user, get_db
from ..intereses import mensual_desde_ea, pago_minimo, simular_pago
from ..models import (
    Cuenta,
    DeudaTarjeta,
    PagoTarjeta,
    Tarjeta,
    TipoTarjeta,
    TipoTransaccion,
    Transaccion,
    Usuario,
)
from ..recurrencia import hoy
from ..schemas import (
    DeudaIn,
    DeudaOut,
    PagoTarjetaIn,
    PagoTarjetaOut,
    SimulacionOut,
    TarjetaConDeudaOut,
    TarjetaIn,
    TarjetaOut,
    TarjetaUpdate,
)
from ..tarjetas import con_deuda, deuda_por_moneda

router = APIRouter(prefix="/tarjetas", tags=["tarjetas"])

CERO = Decimal("0")

# Topes de cordura: ninguna tarjeta colombiana se acerca a esto
TASA_MENSUAL_MAX = Decimal("0.20")  # 20 % mensual
TASA_EA_MAX = Decimal("3")  # 300 % E.A.


def _normalizar_cuenta(db: Session, user: Usuario, tarjeta: Tarjeta) -> None:
    """La cuenta asociada solo aplica al DÉBITO.

    - **Débito**: es un instrumento de una cuenta (activo) → se asocia y debe ser del usuario.
    - **Crédito**: es un pasivo con deuda propia → no se asocia a ninguna cuenta.
    """
    if tarjeta.tipo == TipoTarjeta.CREDITO:
        tarjeta.cuenta_id = None
        return
    if tarjeta.cuenta_id is not None:
        get_owned(db, Cuenta, tarjeta.cuenta_id, user.id)


def _validar_tasa(tarjeta: Tarjeta) -> None:
    """Evita guardar la tasa en la escala equivocada (2,1593 en vez de 0,021593)."""
    if tarjeta.tasa_interes_ea is not None and tarjeta.tasa_interes_ea > TASA_EA_MAX:
        raise HTTPException(
            status_code=400,
            detail=(
                f"La tasa E.A. quedó en {tarjeta.tasa_interes_ea * 100:,.2f} % y eso no es razonable. "
                "Escríbela como el porcentaje del extracto (ej. 29.2215)."
            ),
        )
    if tarjeta.tasa_interes is not None and tarjeta.tasa_interes > TASA_MENSUAL_MAX:
        raise HTTPException(
            status_code=400,
            detail=(
                f"La tasa mensual quedó en {tarjeta.tasa_interes * 100:,.2f} % "
                f"(el máximo razonable es {TASA_MENSUAL_MAX * 100:.0f} %). "
                "Parece que escribiste el porcentaje como número. Usa el selector: "
                "«Mensual (%)» con 2.1593, o «E.A. (% anual)» con 29.2215."
            ),
        )


def _aplicar_tasa(tarjeta: Tarjeta) -> None:
    """Si viene la tasa efectiva anual (como en el extracto), calcula la mensual.

    La mensual es la que usa el simulador de intereses.
    """
    if tarjeta.tasa_interes_ea is not None and tarjeta.tasa_interes_ea > 0:
        tarjeta.tasa_interes = mensual_desde_ea(tarjeta.tasa_interes_ea)


@router.get("", response_model=list[TarjetaConDeudaOut])
def listar(db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    tarjetas = db.scalars(
        select(Tarjeta).where(Tarjeta.usuario_id == user.id).order_by(Tarjeta.nombre)
    ).all()
    return [con_deuda(db, t) for t in tarjetas]


@router.post("", response_model=TarjetaOut, status_code=201)
def crear(data: TarjetaIn, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    obj = Tarjeta(usuario_id=user.id, **data.model_dump())
    _aplicar_tasa(obj)
    _validar_tasa(obj)
    _normalizar_cuenta(db, user, obj)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.get("/{id}", response_model=TarjetaConDeudaOut)
def obtener(id: uuid.UUID, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    return con_deuda(db, get_owned(db, Tarjeta, id, user.id))


@router.patch("/{id}", response_model=TarjetaOut)
def actualizar(id: uuid.UUID, data: TarjetaUpdate, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    obj = get_owned(db, Tarjeta, id, user.id)
    for campo, valor in data.model_dump(exclude_unset=True).items():
        setattr(obj, campo, valor)
    _aplicar_tasa(obj)
    _validar_tasa(obj)
    _normalizar_cuenta(db, user, obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/{id}", status_code=204)
def eliminar(id: uuid.UUID, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    obj = get_owned(db, Tarjeta, id, user.id)
    db.delete(obj)
    db.commit()


# --- deuda de la tarjeta (lo que dice el extracto) ---


@router.get("/{id}/deudas", response_model=list[DeudaOut])
def listar_deudas(id: uuid.UUID, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    get_owned(db, Tarjeta, id, user.id)
    return db.scalars(
        select(DeudaTarjeta)
        .where(DeudaTarjeta.tarjeta_id == id, DeudaTarjeta.usuario_id == user.id)
        .order_by(DeudaTarjeta.fecha.desc())
    ).all()


@router.post("/{id}/deudas", response_model=DeudaOut, status_code=201)
def registrar_deuda(id: uuid.UUID, data: DeudaIn, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    tarjeta = get_owned(db, Tarjeta, id, user.id)
    obj = DeudaTarjeta(
        usuario_id=user.id,
        tarjeta_id=tarjeta.id,
        moneda=data.moneda,
        monto=data.monto,
        fecha=data.fecha or hoy(),
        notas=data.notas,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/{id}/deudas/{deuda_id}", status_code=204)
def eliminar_deuda(id: uuid.UUID, deuda_id: uuid.UUID, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    get_owned(db, Tarjeta, id, user.id)
    obj = get_owned(db, DeudaTarjeta, deuda_id, user.id)
    db.delete(obj)
    db.commit()


@router.get("/{id}/pagos", response_model=list[PagoTarjetaOut])
def listar_pagos(id: uuid.UUID, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    get_owned(db, Tarjeta, id, user.id)
    return db.scalars(
        select(PagoTarjeta)
        .where(PagoTarjeta.tarjeta_id == id, PagoTarjeta.usuario_id == user.id)
        .order_by(PagoTarjeta.fecha.desc())
    ).all()


@router.post("/{id}/pagos", response_model=TarjetaConDeudaOut, status_code=201)
def pagar(
    id: uuid.UUID,
    data: PagoTarjetaIn,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """Registra un pago de la tarjeta: baja la cuenta **y** la deuda.

    Devuelve la tarjeta ya actualizada, para que la UI muestre la deuda vigente.
    El pago se guarda además como una **transferencia** de la cuenta a la tarjeta:
    pagar una deuda propia no es un gasto, así que no entra en los reportes por
    categoría ni en el flujo de caja (el consumo ya se contó al comprar).
    """
    tarjeta = get_owned(db, Tarjeta, id, user.id)
    if tarjeta.tipo != TipoTarjeta.CREDITO:
        raise HTTPException(
            status_code=422,
            detail=(
                f"«{tarjeta.nombre}» es de débito: no genera deuda que pagar, su saldo "
                "es el de la cuenta asociada"
            ),
        )

    cuenta = get_owned(db, Cuenta, data.cuenta_id, user.id)
    if cuenta.moneda != data.moneda:
        raise HTTPException(
            status_code=422,
            detail=(
                f"La cuenta está en {cuenta.moneda} y el pago en {data.moneda}: "
                "elige la cuenta de esa moneda"
            ),
        )

    # No se puede pagar más de lo que se debe en esa moneda
    _, _, vigente = deuda_por_moneda(db, tarjeta)
    deuda = Decimal(str(vigente.get(data.moneda, 0.0)))
    if deuda <= CERO:
        raise HTTPException(
            status_code=422,
            detail=(
                f"«{tarjeta.nombre}» no tiene deuda registrada en {data.moneda}. "
                "Registra primero lo que dice el extracto y luego el pago."
            ),
        )
    if data.monto > deuda:
        raise HTTPException(
            status_code=422,
            detail=(
                f"El pago ({data.monto}) supera la deuda en {data.moneda} ({deuda}). "
                "Si de verdad pagaste de más, registra el extracto nuevo con el saldo real."
            ),
        )

    fecha = data.fecha or hoy()
    transaccion = Transaccion(
        usuario_id=user.id,
        tipo=TipoTransaccion.TRANSFERENCIA,
        monto=data.monto,
        moneda=data.moneda,
        fecha=fecha,
        descripcion=f"Pago tarjeta {tarjeta.nombre}",
        cuenta_id=cuenta.id,
        tarjeta_id=tarjeta.id,
        notas=data.notas,
    )
    db.add(transaccion)
    db.flush()

    pago = PagoTarjeta(
        usuario_id=user.id,
        tarjeta_id=tarjeta.id,
        cuenta_id=cuenta.id,
        transaccion_id=transaccion.id,
        monto=data.monto,
        moneda=data.moneda,
        fecha=fecha,
        notas=data.notas,
    )
    db.add(pago)
    db.commit()
    db.refresh(tarjeta)
    return con_deuda(db, tarjeta)


@router.delete("/{id}/pagos/{pago_id}", status_code=204)
def eliminar_pago(
    id: uuid.UUID, pago_id: uuid.UUID, db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """Deshace un pago: quita el movimiento y devuelve la deuda a como estaba."""
    get_owned(db, Tarjeta, id, user.id)
    pago = get_owned(db, PagoTarjeta, pago_id, user.id)
    if pago.transaccion_id is not None:
        transaccion = db.get(Transaccion, pago.transaccion_id)
        if transaccion is not None and transaccion.usuario_id == user.id:
            db.delete(transaccion)
    db.delete(pago)
    db.commit()


@router.get("/{id}/simulador", response_model=SimulacionOut)
def simular(
    id: uuid.UUID,
    saldo: float | None = None,
    pago_mensual: float | None = None,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """Simula el pago de la deuda. Si no se indica saldo, usa la deuda registrada.

    Si no se indica `pago_mensual`, se usa el 5% del saldo como pago mínimo.
    """
    tarjeta = get_owned(db, Tarjeta, id, user.id)
    if tarjeta.tasa_interes is None:
        raise HTTPException(status_code=400, detail="La tarjeta no tiene tasa de interés configurada")

    if saldo is None:
        saldo = con_deuda(db, tarjeta)["deuda_total_cop"]
        if saldo is None:
            raise HTTPException(
                status_code=400,
                detail="No hay deuda registrada (o falta la tasa de cambio). Registra la deuda o indica el saldo.",
            )

    saldo_d = Decimal(str(saldo))
    if saldo_d <= 0:
        raise HTTPException(status_code=400, detail="El saldo debe ser mayor que cero")
    pago_d = Decimal(str(pago_mensual)) if pago_mensual else pago_minimo(saldo_d)

    return simular_pago(saldo_d, tarjeta.tasa_interes, pago_d)
