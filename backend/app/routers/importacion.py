"""Importación de estados de cuenta (CSV): previsualizar y confirmar."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from ..deps import get_current_user, get_db
from ..importacion import parsear_csv
from ..models import Transaccion, Usuario
from ..schemas import ImportarConfirmarIn, ImportarPreviewOut, ImportarResultadoOut

router = APIRouter(prefix="/importar", tags=["importar"])


@router.post("/csv", response_model=ImportarPreviewOut)
async def previsualizar(
    archivo: UploadFile = File(...),
    tipo_default: str = "gasto",
    user: Usuario = Depends(get_current_user),
):
    """Parsea el CSV y devuelve las filas detectadas (sin guardar nada)."""
    contenido = (await archivo.read()).decode("utf-8", errors="replace")
    filas = parsear_csv(contenido, tipo_default)
    return {"filas": filas, "total": len(filas)}


@router.post("/confirmar", response_model=ImportarResultadoOut)
def confirmar(data: ImportarConfirmarIn, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    """Crea las transacciones de las filas previsualizadas."""
    if not data.filas:
        raise HTTPException(status_code=400, detail="No hay filas para importar")
    for f in data.filas:
        db.add(
            Transaccion(
                usuario_id=user.id,
                tipo=f.tipo,
                monto=f.monto,
                moneda=f.moneda,
                fecha=f.fecha,
                descripcion=f.descripcion,
                categoria_id=f.categoria_id,
            )
        )
    db.commit()
    return {"creadas": len(data.filas)}
