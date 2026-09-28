"""CRUD de pólizas de seguro (personas y vehículos) y sus beneficiarios.

Una póliza es un compromiso recurrente como una suscripción —tiene prima,
periodicidad y `proximo_pago`, y el scheduler genera el gasto al vencer— más la
**vigencia** (para avisar del vencimiento) y los datos del **bien asegurado**
(vehículo: placa, marca, modelo y valor asegurado).

    GET    /polizas                              -> listado (con beneficiarios)
    POST   /polizas
    GET    /polizas/resumen                      -> costo mensual/anual en COP
    POST   /polizas/{id}/beneficiarios
    PATCH  /polizas/beneficiarios/{beneficiario_id}
    DELETE /polizas/beneficiarios/{beneficiario_id}
    GET    /polizas/{id}
    PATCH  /polizas/{id}
    DELETE /polizas/{id}
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..crud_utils import get_owned
from ..deps import get_current_user, get_db
from ..models import (
    Beneficiario,
    Categoria,
    Cuenta,
    EstadoSuscripcion,
    Etiqueta,
    Poliza,
    Tarjeta,
    Usuario,
)
from ..recurrencia import factor_mensual
from ..schemas import (
    BeneficiarioIn,
    BeneficiarioOut,
    PolizaIn,
    PolizaOut,
    PolizaResumenOut,
    PolizaUpdate,
)
from ..tasas import convertir

router = APIRouter(prefix="/polizas", tags=["polizas"])


# --- helpers --------------------------------------------------------------- #


def _validar_refs(db: Session, user: Usuario, campos: dict) -> None:
    """Categoría, etiqueta, tarjeta y cuenta deben existir y ser del usuario."""
    for campo, modelo in (
        ("categoria_id", Categoria),
        ("etiqueta_id", Etiqueta),
        ("tarjeta_id", Tarjeta),
        ("cuenta_id", Cuenta),
    ):
        valor = campos.get(campo)
        if valor is not None:
            get_owned(db, modelo, valor, user.id)


def _prima_mensual_cop(db: Session, pol: Poliza) -> float | None:
    """Prima llevada a mes y a COP. `None` si no hay tasa para su moneda."""
    monto = Decimal(str(pol.prima)) * factor_mensual(pol.periodicidad)
    if pol.moneda != "COP":
        convertido = convertir(db, pol.moneda, "COP", monto)
        if convertido is None:
            return None  # sin tasa no se puede sumar con honestidad
        monto = convertido
    return float(monto.quantize(Decimal("0.01")))


def _beneficiarios_por_poliza(db: Session, usuario_id, poliza_ids: list) -> dict:
    if not poliza_ids:
        return {}
    filas = db.scalars(
        select(Beneficiario)
        .where(
            Beneficiario.usuario_id == usuario_id,
            Beneficiario.poliza_id.in_(poliza_ids),
        )
        .order_by(Beneficiario.creada_en)
    ).all()
    agrupados: dict = {}
    for b in filas:
        agrupados.setdefault(b.poliza_id, []).append(b)
    return agrupados


def _salida(db: Session, pol: Poliza, beneficiarios: list) -> PolizaOut:
    out = PolizaOut.model_validate(pol)
    out.beneficiarios = [BeneficiarioOut.model_validate(b) for b in beneficiarios]
    out.prima_mensual_cop = _prima_mensual_cop(db, pol)
    return out


def _suma_porcentajes(db: Session, poliza_id, excluir: uuid.UUID | None = None) -> Decimal:
    filas = db.scalars(
        select(Beneficiario).where(
            Beneficiario.poliza_id == poliza_id, Beneficiario.porcentaje.is_not(None)
        )
    ).all()
    return sum(
        (Decimal(str(b.porcentaje)) for b in filas if b.id != excluir), Decimal("0")
    )


# --- pólizas --------------------------------------------------------------- #


@router.get("", response_model=list[PolizaOut])
def listar(db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    polizas = db.scalars(
        select(Poliza)
        .where(Poliza.usuario_id == user.id)
        .order_by(Poliza.proximo_pago.asc().nulls_last(), Poliza.aseguradora)
    ).all()
    bens = _beneficiarios_por_poliza(db, user.id, [p.id for p in polizas])
    return [_salida(db, p, bens.get(p.id, [])) for p in polizas]


@router.get("/resumen", response_model=PolizaResumenOut)
def resumen(db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    """Cuánto cuestan los seguros activos, normalizado a COP."""
    activas = db.scalars(
        select(Poliza).where(
            Poliza.usuario_id == user.id, Poliza.estado == EstadoSuscripcion.ACTIVA
        )
    ).all()
    mensual = Decimal("0")
    sin_tasa: list[str] = []
    for pol in activas:
        valor = _prima_mensual_cop(db, pol)
        if valor is None:
            if pol.moneda not in sin_tasa:
                sin_tasa.append(pol.moneda)
            continue
        mensual += Decimal(str(valor))
    mensual = mensual.quantize(Decimal("0.01"))
    return PolizaResumenOut(
        polizas_activas=len(activas),
        prima_mensual_cop=float(mensual),
        prima_anual_cop=float((mensual * 12).quantize(Decimal("0.01"))),
        sin_tasa=sin_tasa,
    )


@router.post("", response_model=PolizaOut, status_code=201)
def crear(
    data: PolizaIn,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    campos = data.model_dump()
    _validar_refs(db, user, campos)
    pol = Poliza(usuario_id=user.id, **campos)
    db.add(pol)
    db.commit()
    db.refresh(pol)
    return _salida(db, pol, [])


@router.post("/{id}/beneficiarios", response_model=BeneficiarioOut, status_code=201)
def agregar_beneficiario(
    id: uuid.UUID,
    data: BeneficiarioIn,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    pol = get_owned(db, Poliza, id, user.id)
    if data.porcentaje is not None:
        total = _suma_porcentajes(db, pol.id) + Decimal(str(data.porcentaje))
        if total > 100:
            raise HTTPException(
                status_code=400,
                detail=f"Los porcentajes de los beneficiarios suman {total}; no pueden pasar de 100",
            )
    ben = Beneficiario(usuario_id=user.id, poliza_id=pol.id, **data.model_dump())
    db.add(ben)
    db.commit()
    db.refresh(ben)
    return ben


@router.patch("/beneficiarios/{beneficiario_id}", response_model=BeneficiarioOut)
def editar_beneficiario(
    beneficiario_id: uuid.UUID,
    data: BeneficiarioIn,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    ben = get_owned(db, Beneficiario, beneficiario_id, user.id)
    campos = data.model_dump()
    if campos.get("porcentaje") is not None:
        total = _suma_porcentajes(db, ben.poliza_id, excluir=ben.id) + Decimal(
            str(campos["porcentaje"])
        )
        if total > 100:
            raise HTTPException(
                status_code=400,
                detail=f"Los porcentajes de los beneficiarios suman {total}; no pueden pasar de 100",
            )
    for campo, valor in campos.items():
        setattr(ben, campo, valor)
    db.commit()
    db.refresh(ben)
    return ben


@router.delete("/beneficiarios/{beneficiario_id}", status_code=204)
def eliminar_beneficiario(
    beneficiario_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    ben = get_owned(db, Beneficiario, beneficiario_id, user.id)
    db.delete(ben)
    db.commit()


@router.get("/{id}", response_model=PolizaOut)
def obtener(
    id: uuid.UUID, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)
):
    pol = get_owned(db, Poliza, id, user.id)
    bens = _beneficiarios_por_poliza(db, user.id, [pol.id])
    return _salida(db, pol, bens.get(pol.id, []))


@router.patch("/{id}", response_model=PolizaOut)
def actualizar(
    id: uuid.UUID,
    data: PolizaUpdate,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    pol = get_owned(db, Poliza, id, user.id)
    campos = data.model_dump(exclude_unset=True)
    _validar_refs(db, user, campos)
    for campo, valor in campos.items():
        setattr(pol, campo, valor)
    db.commit()
    db.refresh(pol)
    bens = _beneficiarios_por_poliza(db, user.id, [pol.id])
    return _salida(db, pol, bens.get(pol.id, []))


@router.delete("/{id}", status_code=204)
def eliminar(
    id: uuid.UUID, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)
):
    pol = get_owned(db, Poliza, id, user.id)
    db.delete(pol)
    db.commit()
