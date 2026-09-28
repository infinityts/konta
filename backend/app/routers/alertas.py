"""Alertas de pagos próximos (suscripciones y tarjetas)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..alertas import calcular_alertas
from ..deps import get_current_user, get_db
from ..models import Usuario
from ..schemas import AlertaOut

router = APIRouter(prefix="/alertas", tags=["alertas"])


@router.get("", response_model=list[AlertaOut])
def listar(dias: int = 15, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    """Próximos pagos dentro de `dias` (incluye vencidos si son recientes)."""
    return calcular_alertas(db, user.id, dias)
