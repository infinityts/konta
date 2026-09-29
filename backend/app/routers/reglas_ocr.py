"""Reglas de OCR aprendidas: verlas, corregirlas y borrarlas.

El clasificador **aprende** de cada corrección del usuario (`reglas_ocr`), pero ese
aprendizaje era de una sola dirección: no se podía ver qué sabía ni deshacer un
acierto equivocado. Aquí está el CRUD que faltaba.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..clasificador import normalizar
from ..crud_utils import get_owned
from ..deps import get_current_user, get_db
from ..models import Categoria, Etiqueta, ReglaOcr, Usuario
from ..schemas import ReglaOcrIn, ReglaOcrOut, ReglaOcrUpdate

router = APIRouter(prefix="/reglas-ocr", tags=["reglas-ocr"])


def _patron(texto: str) -> str:
    """Normaliza igual que al aprender, para que la regla empareje de verdad."""
    patron = normalizar(texto)
    if not patron:
        raise HTTPException(
            status_code=422,
            detail="El patrón queda vacío después de normalizarlo (mayúsculas y sin acentos)",
        )
    return patron


def _existe(db: Session, user: Usuario, patron: str, excluir: uuid.UUID | None = None) -> bool:
    consulta = select(ReglaOcr).where(
        ReglaOcr.usuario_id == user.id, ReglaOcr.patron == patron
    )
    if excluir is not None:
        consulta = consulta.where(ReglaOcr.id != excluir)
    return db.scalar(consulta) is not None


def _salida(db: Session, regla: ReglaOcr) -> ReglaOcrOut:
    """Regla + dónde cae (`Categoría › Etiqueta`), para que la interfaz lo muestre."""
    etiqueta = db.get(Etiqueta, regla.etiqueta_id)
    categoria = db.get(Categoria, etiqueta.categoria_id) if etiqueta else None
    return ReglaOcrOut(
        id=regla.id,
        patron=regla.patron,
        etiqueta_id=regla.etiqueta_id,
        etiqueta_nombre=etiqueta.nombre if etiqueta else None,
        categoria_id=categoria.id if categoria else None,
        categoria_nombre=categoria.nombre if categoria else None,
        veces_usada=regla.veces_usada,
        creada_en=regla.creada_en,
        actualizada_en=regla.actualizada_en,
    )


@router.get("", response_model=list[ReglaOcrOut])
def listar(db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    """Lo que el clasificador ha aprendido, de lo más reciente a lo más antiguo."""
    reglas = db.scalars(
        select(ReglaOcr)
        .where(ReglaOcr.usuario_id == user.id)
        .order_by(ReglaOcr.actualizada_en.desc())
    ).all()
    return [_salida(db, r) for r in reglas]


@router.post("", response_model=ReglaOcrOut, status_code=201)
def crear(data: ReglaOcrIn, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    """Enseña una regla a mano (sin esperar a corregir una línea)."""
    patron = _patron(data.patron)
    get_owned(db, Etiqueta, data.etiqueta_id, user.id)
    if _existe(db, user, patron):
        raise HTTPException(
            status_code=400,
            detail=f"Ya existe una regla para «{patron}»: edítala en vez de crear otra",
        )

    regla = ReglaOcr(usuario_id=user.id, patron=patron, etiqueta_id=data.etiqueta_id)
    db.add(regla)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Ya existe una regla para «{patron}»") from None
    db.refresh(regla)
    return _salida(db, regla)


@router.get("/{id}", response_model=ReglaOcrOut)
def obtener(id: uuid.UUID, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    return _salida(db, get_owned(db, ReglaOcr, id, user.id))


@router.patch("/{id}", response_model=ReglaOcrOut)
def actualizar(
    id: uuid.UUID,
    data: ReglaOcrUpdate,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """Corrige el aprendizaje: cambia el patrón, la etiqueta o las dos cosas."""
    regla = get_owned(db, ReglaOcr, id, user.id)
    campos = data.model_dump(exclude_unset=True)

    if campos.get("patron") is not None:
        patron = _patron(campos["patron"])
        if _existe(db, user, patron, excluir=regla.id):
            raise HTTPException(
                status_code=400, detail=f"Ya tienes otra regla para «{patron}»"
            )
        regla.patron = patron
    if campos.get("etiqueta_id") is not None:
        get_owned(db, Etiqueta, campos["etiqueta_id"], user.id)
        regla.etiqueta_id = campos["etiqueta_id"]

    regla.actualizada_en = datetime.now(UTC)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=400, detail="Ya tienes otra regla con ese patrón"
        ) from None
    db.refresh(regla)
    return _salida(db, regla)


@router.delete("/{id}", status_code=204)
def eliminar(id: uuid.UUID, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    """Deshace el aprendizaje: a partir de aquí el artículo vuelve a clasificarse solo."""
    regla = get_owned(db, ReglaOcr, id, user.id)
    db.delete(regla)
    db.commit()
