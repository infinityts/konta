"""Trabajo diario de mantenimiento: lo que hay que revisar una vez al día.

Se junta aquí para que el planificador tenga **una** tarea diaria y no cinco: los planes de pago
que vencen, las propuestas del asistente que ya no tienen sentido y lo que se pueda ir sumando.
Cada pieza es idempotente por su cuenta.
"""

from __future__ import annotations

from .db import make_engine, make_session_factory
from .pagos import vencer_planes
from .propuestas import expirar_viejas


def mantenimiento_diario() -> dict:
    """Corre el mantenimiento del día y devuelve qué hizo (para los registros)."""
    engine = make_engine()
    sf = make_session_factory(engine)
    try:
        with sf.begin() as s:
            planes = len(vencer_planes(s))
            propuestas = expirar_viejas(s)
        return {"planes_vencidos": planes, "propuestas_expiradas": propuestas}
    finally:
        engine.dispose()
