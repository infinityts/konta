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
from ..models import Cuenta, DeudaTarjeta, Tarjeta, TipoTarjeta, Usuario
from ..recurrencia import hoy
from ..schemas import (
    DeudaIn,
    DeudaOut,
    SimulacionOut,
    TarjetaConDeudaOut,
    TarjetaIn,
    TarjetaOut,
    TarjetaUpdate,
)
from ..tasas import obtener_tasa

router = APIRouter(prefix="/tarjetas", tags=["tarjetas"])

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


def _con_deuda(db: Session, tarjeta: Tarjeta) -> dict:
    """Tarjeta + deuda por moneda + total en COP (si hay tasas para convertir)."""
    deudas = db.scalars(
        select(DeudaTarjeta)
        .where(DeudaTarjeta.tarjeta_id == tarjeta.id, DeudaTarjeta.usuario_id == tarjeta.usuario_id)
        .order_by(DeudaTarjeta.fecha.desc())
    ).all()

    por_moneda: dict[str, float] = {}
    for d in deudas:
        por_moneda[d.moneda] = por_moneda.get(d.moneda, 0.0) + float(d.monto)

    total_cop = 0.0
    completo = True
    for moneda, monto in por_moneda.items():
        if moneda == "COP":
            total_cop += monto
            continue
        tasa = obtener_tasa(db, moneda, "COP")
        if tasa is None:
            completo = False
            break
        total_cop += monto * float(tasa)

    nombre_cuenta = None
    if tarjeta.cuenta_id:
        cuenta = db.get(Cuenta, tarjeta.cuenta_id)
        nombre_cuenta = cuenta.nombre if cuenta else None

    return {
        "id": tarjeta.id,
        "usuario_id": tarjeta.usuario_id,
        "nombre": tarjeta.nombre,
        "banco": tarjeta.banco,
        "tipo": tarjeta.tipo,
        "moneda": tarjeta.moneda,
        "dia_corte": tarjeta.dia_corte,
        "dia_pago": tarjeta.dia_pago,
        "limite": tarjeta.limite,
        "tasa_interes": tarjeta.tasa_interes,
        "tasa_interes_ea": tarjeta.tasa_interes_ea,
        "cuenta_id": tarjeta.cuenta_id,
        "cuenta_nombre": nombre_cuenta,
        "activa": tarjeta.activa,
        "deudas": deudas,
        "deuda_por_moneda": por_moneda,
        "deuda_total_cop": round(total_cop, 2) if completo else None,
    }


@router.get("", response_model=list[TarjetaConDeudaOut])
def listar(db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    tarjetas = db.scalars(
        select(Tarjeta).where(Tarjeta.usuario_id == user.id).order_by(Tarjeta.nombre)
    ).all()
    return [_con_deuda(db, t) for t in tarjetas]


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
    return _con_deuda(db, get_owned(db, Tarjeta, id, user.id))


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
        saldo = _con_deuda(db, tarjeta)["deuda_total_cop"]
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
