"""Reportes de finanzas (mensual y por categoría)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..deps import get_current_user, get_db
from ..models import Usuario
from ..recurrencia import hoy
from ..reportes import reporte_categorias, reporte_mensual
from ..schemas import ReporteCategoriaOut, ReporteMesOut

router = APIRouter(prefix="/reportes", tags=["reportes"])


@router.get("/mensual", response_model=list[ReporteMesOut])
def mensual(meses: int = 6, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    return reporte_mensual(db, user.id, meses)


@router.get("/categorias", response_model=list[ReporteCategoriaOut])
def categorias(mes: str | None = None, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    mes = mes or hoy().strftime("%Y-%m")
    return reporte_categorias(db, user.id, mes)
