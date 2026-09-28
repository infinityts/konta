"""Helpers compartidos por los routers."""

from __future__ import annotations

import uuid

from fastapi import HTTPException
from sqlalchemy.orm import Session


def get_owned(db: Session, model, id: uuid.UUID, usuario_id: uuid.UUID):
    """Devuelve un recurso solo si pertenece al usuario; si no, 404."""
    obj = db.get(model, id)
    if obj is None or obj.usuario_id != usuario_id:
        raise HTTPException(status_code=404, detail="Recurso no encontrado")
    return obj
