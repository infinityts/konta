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
    Etiqueta,
    Poliza,
    PolizaAsegurado,
    Tarjeta,
    Usuario,
)
from ..polizas import prima_mensual_cop
from ..polizas import resumen as resumen_polizas
from ..schemas import (
    AseguradoIn,
    AseguradoOut,
    BeneficiarioIn,
    BeneficiarioOut,
    PolizaIn,
    PolizaOut,
    PolizaResumenOut,
    PolizaUpdate,
)

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


def _asegurados_por_poliza(db: Session, usuario_id, poliza_ids: list) -> dict:
    if not poliza_ids:
        return {}
    filas = db.scalars(
        select(PolizaAsegurado)
        .where(
            PolizaAsegurado.usuario_id == usuario_id,
            PolizaAsegurado.poliza_id.in_(poliza_ids),
        )
        .order_by(PolizaAsegurado.es_titular.desc(), PolizaAsegurado.creada_en)
    ).all()
    agrupados: dict = {}
    for a in filas:
        agrupados.setdefault(a.poliza_id, []).append(a)
    return agrupados


def _salida(
    db: Session, pol: Poliza, beneficiarios: list, asegurados: list | None = None
) -> PolizaOut:
    out = PolizaOut.model_validate(pol)
    out.beneficiarios = [BeneficiarioOut.model_validate(b) for b in beneficiarios]
    out.asegurados = [AseguradoOut.model_validate(a) for a in (asegurados or [])]
    out.prima_mensual_cop = prima_mensual_cop(db, pol)
    return out


def _marcar_titular_unico(db: Session, poliza_id, asegurado_id, es_titular: bool) -> None:
    """Solo puede haber un titular por póliza: al marcarlo, se desmarca el resto."""
    if not es_titular:
        return
    otros = db.scalars(
        select(PolizaAsegurado).where(
            PolizaAsegurado.poliza_id == poliza_id,
            PolizaAsegurado.id != asegurado_id,
            PolizaAsegurado.es_titular.is_(True),
        )
    ).all()
    for otro in otros:
        otro.es_titular = False


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
    asegs = _asegurados_por_poliza(db, user.id, [p.id for p in polizas])
    return [
        _salida(db, p, bens.get(p.id, []), asegs.get(p.id, []))
        for p in polizas
    ]


@router.get("/resumen", response_model=PolizaResumenOut)
def resumen(db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    """Cuánto cuestan los seguros activos, normalizado a COP."""
    return resumen_polizas(db, user.id)


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


@router.post("/{id}/asegurados", response_model=AseguradoOut, status_code=201)
def agregar_asegurado(
    id: uuid.UUID,
    data: AseguradoIn,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """Añade una persona cubierta por la póliza (una póliza familiar cubre a varias)."""
    pol = get_owned(db, Poliza, id, user.id)
    asegurado = PolizaAsegurado(usuario_id=user.id, poliza_id=pol.id, **data.model_dump())
    db.add(asegurado)
    db.flush()
    _marcar_titular_unico(db, pol.id, asegurado.id, asegurado.es_titular)
    db.commit()
    db.refresh(asegurado)
    return asegurado


@router.patch("/asegurados/{asegurado_id}", response_model=AseguradoOut)
def editar_asegurado(
    asegurado_id: uuid.UUID,
    data: AseguradoIn,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    asegurado = get_owned(db, PolizaAsegurado, asegurado_id, user.id)
    for campo, valor in data.model_dump().items():
        setattr(asegurado, campo, valor)
    db.flush()
    _marcar_titular_unico(db, asegurado.poliza_id, asegurado.id, asegurado.es_titular)
    db.commit()
    db.refresh(asegurado)
    return asegurado


@router.delete("/asegurados/{asegurado_id}", status_code=204)
def eliminar_asegurado(
    asegurado_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    asegurado = get_owned(db, PolizaAsegurado, asegurado_id, user.id)
    db.delete(asegurado)
    db.commit()


@router.get("/{id}", response_model=PolizaOut)
def obtener(
    id: uuid.UUID, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)
):
    pol = get_owned(db, Poliza, id, user.id)
    bens = _beneficiarios_por_poliza(db, user.id, [pol.id])
    asegs = _asegurados_por_poliza(db, user.id, [pol.id])
    return _salida(db, pol, bens.get(pol.id, []), asegs.get(pol.id, []))


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
    asegs = _asegurados_por_poliza(db, user.id, [pol.id])
    return _salida(db, pol, bens.get(pol.id, []), asegs.get(pol.id, []))


@router.delete("/{id}", status_code=204)
def eliminar(
    id: uuid.UUID, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)
):
    pol = get_owned(db, Poliza, id, user.id)
    db.delete(pol)
    db.commit()
