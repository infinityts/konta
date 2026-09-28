"""CRUD de ingresos recurrentes (aislado por usuario)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..crud_utils import get_owned
from ..deps import get_current_user, get_db
from ..models import Categoria, Cuenta, IngresoRecurrente, Usuario
from ..recurrencia import proxima_ocurrencia_inicial
from ..schemas import IngresoRecurrenteIn, IngresoRecurrenteOut, IngresoRecurrenteUpdate

router = APIRouter(prefix="/ingresos-recurrentes", tags=["ingresos recurrentes"])


def _validar_refs(db: Session, user: Usuario, campos: dict) -> None:
    """Categoría y cuenta deben existir y ser del usuario."""
    for campo, modelo in (("categoria_id", Categoria), ("cuenta_id", Cuenta)):
        valor = campos.get(campo)
        if valor is not None:
            get_owned(db, modelo, valor, user.id)


@router.get("", response_model=list[IngresoRecurrenteOut])
def listar(db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    return db.scalars(
        select(IngresoRecurrente)
        .where(IngresoRecurrente.usuario_id == user.id)
        .order_by(IngresoRecurrente.proxima_ejecucion.asc())
    ).all()


@router.post("", response_model=IngresoRecurrenteOut, status_code=201)
def crear(data: IngresoRecurrenteIn, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    _validar_refs(db, user, data.model_dump())
    obj = IngresoRecurrente(
        usuario_id=user.id,
        **data.model_dump(exclude={"periodicidad", "dia"}),
        periodicidad=data.periodicidad,
        dia=data.dia if data.periodicidad.value != "diario" else None,
        proxima_ejecucion=proxima_ocurrencia_inicial(data.periodicidad, data.dia),
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.get("/{id}", response_model=IngresoRecurrenteOut)
def obtener(id: uuid.UUID, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    return get_owned(db, IngresoRecurrente, id, user.id)


@router.patch("/{id}", response_model=IngresoRecurrenteOut)
def actualizar(id: uuid.UUID, data: IngresoRecurrenteUpdate, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    obj = get_owned(db, IngresoRecurrente, id, user.id)
    cambios = data.model_dump(exclude_unset=True)
    _validar_refs(db, user, cambios)
    for campo, valor in cambios.items():
        if campo != "periodicidad":
            setattr(obj, campo, valor)
    # Si cambia periodicidad/día, recalcular la próxima ejecución
    if "periodicidad" in cambios or "dia" in cambios:
        obj.periodicidad = cambios.get("periodicidad", obj.periodicidad)
        dia = cambios.get("dia", obj.dia)
        obj.dia = dia if obj.periodicidad.value != "diario" else None
        obj.proxima_ejecucion = proxima_ocurrencia_inicial(obj.periodicidad, obj.dia)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/{id}", status_code=204)
def eliminar(id: uuid.UUID, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    obj = get_owned(db, IngresoRecurrente, id, user.id)
    db.delete(obj)
    db.commit()
