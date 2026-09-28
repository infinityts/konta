"""Exportar/restaurar datos del usuario (respaldo)."""

from __future__ import annotations

import csv
import io
import json

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..deps import get_current_user, get_db
from ..models import Transaccion, Usuario
from ..respaldo import exportar, restaurar

router = APIRouter(tags=["respaldo"])


@router.get("/exportar/json")
def exportar_json(db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    """Descarga un respaldo completo en JSON."""
    contenido = json.dumps(exportar(db, user.id), default=str, ensure_ascii=False, indent=2)
    return Response(
        content=contenido,
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="konta-respaldo.json"'},
    )


@router.get("/exportar/transacciones.csv")
def exportar_transacciones_csv(db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    """Descarga las transacciones en CSV."""
    filas = db.scalars(
        select(Transaccion).where(Transaccion.usuario_id == user.id).order_by(Transaccion.fecha)
    ).all()
    buf = io.StringIO()
    escritor = csv.writer(buf)
    escritor.writerow(
        ["fecha", "tipo", "monto", "moneda", "descripcion", "categoria_id", "tarjeta_id", "etiqueta_id"]
    )
    for t in filas:
        escritor.writerow(
            [
                t.fecha.isoformat(),
                t.tipo.value,
                str(t.monto),
                t.moneda,
                t.descripcion or "",
                str(t.categoria_id) if t.categoria_id else "",
                str(t.tarjeta_id) if t.tarjeta_id else "",
                str(t.etiqueta_id) if t.etiqueta_id else "",
            ]
        )
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="konta-transacciones.csv"'},
    )


@router.post("/respaldar/restaurar")
async def restaurar_respaldo(
    archivo: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """Restaura los datos del usuario desde un respaldo JSON (reemplaza lo actual)."""
    contenido = await archivo.read()
    try:
        datos = json.loads(contenido.decode("utf-8"))
    except Exception:  # noqa: BLE001 — un JSON inválido es un 400, no un error del servidor
        raise HTTPException(
            status_code=400, detail="El archivo no es un respaldo JSON válido"
        ) from None
    if not isinstance(datos, dict):
        raise HTTPException(status_code=400, detail="Formato de respaldo inválido")

    resultado = restaurar(db, user.id, datos)
    return {"restaurado": resultado}
