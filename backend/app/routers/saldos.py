"""Saldo total, consolidado mes a mes y diagnóstico del sobregiro."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..deps import get_current_user, get_db
from ..models import Usuario
from ..saldos import consolidado, diagnostico, saldo_cuentas
from ..schemas import ConsolidadoOut, DiagnosticoOut, SaldoResumenOut

router = APIRouter(prefix="/saldos", tags=["saldos"])


@router.get("", response_model=SaldoResumenOut)
def resumen(db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    """Saldo actual por cuenta y total."""
    return saldo_cuentas(db, user.id)


@router.get("/consolidado", response_model=ConsolidadoOut)
def consolidado_endpoint(
    meses: int = 6,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """Consolidado mes a mes con saldo inicial, balance y saldo final corrido."""
    return consolidado(db, user.id, meses)


@router.get("/diagnostico", response_model=DiagnosticoOut)
def diagnostico_endpoint(db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    """Estado del saldo y el motivo (si estás sobregirado)."""
    return diagnostico(db, user.id)
