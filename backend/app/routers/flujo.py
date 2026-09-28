"""Proyección de flujo de caja."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..deps import get_current_user, get_db
from ..flujo import proyectar
from ..models import Usuario
from ..schemas import FlujoCajaOut

router = APIRouter(prefix="/flujo-caja", tags=["flujo"])


@router.get("", response_model=FlujoCajaOut)
def flujo(meses: int = 6, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    return proyectar(db, user.id, meses)
