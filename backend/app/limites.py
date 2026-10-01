"""El freno de uso en lo que **cuesta dinero**.

Cada consulta al asistente y cada lectura con IA las pagamos nosotros, así que un script (o un
cliente con un bucle de reintentos) puede gastar en un minuto lo que el plan cobra por un mes. Esto
**no** es el tope del plan —eso lo pone la cuota— sino un freno a ir muy rápido:

- **Contador por ventana**: una fila por clave con el inicio de la ventana y cuántos usos lleva. Al
  pasar la ventana se reinicia sola, sin guardar cada llamada ni limpiar nada.
- **Claves distintas según el riesgo**: al registrarse se cuenta por **IP** (crear cuentas en serie es
  el hueco de verdad: cada cuenta trae plan gratis que pagamos nosotros) y al usar la IA por
  **usuario**.
- **Frena antes de tocar la cuota**: si te frena por ir rápido, **no** se te gasta la consulta del
  plan. Y se hace en un solo paso (se reserva la fila, se cuenta y se decide), que es la lección de
  estas rondas: comprobar y escribir tienen que ser lo mismo.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .models import LimiteUso


def revisar(
    db: Session,
    clave: str,
    limite: int,
    segundos: int,
    que: str = "esa acción",
) -> None:
    """Suma un uso de `clave` y frena (429) si pasa del límite en la ventana."""
    if limite <= 0:
        return
    ahora = datetime.now(UTC)
    fila = db.scalar(select(LimiteUso).where(LimiteUso.clave == clave).with_for_update())
    if fila is None:
        fila = LimiteUso(clave=clave, ventana_inicio=ahora, usos=0)
        db.add(fila)
        try:
            db.flush()
        except IntegrityError:
            # Dos peticiones a la vez creando la misma clave: la segunda se queda con la fila
            db.rollback()
            fila = db.scalar(select(LimiteUso).where(LimiteUso.clave == clave).with_for_update())
            if fila is None:  # pragma: no cover — no debería pasar
                return

    # Si la ventana ya pasó, se empieza de cero
    if fila.ventana_inicio is None or fila.ventana_inicio <= ahora - timedelta(seconds=segundos):
        fila.ventana_inicio, fila.usos = ahora, 0

    fila.usos += 1
    if fila.usos > limite:
        faltan = max(1, int((fila.ventana_inicio + timedelta(seconds=segundos) - ahora).total_seconds()) + 1)
        db.commit()
        raise HTTPException(
            status_code=429,
            detail=(
                f"Vas muy rápido con {que}: espera {faltan} segundo"
                f"{'s' if faltan != 1 else ''} y vuelve a intentarlo. "
                "No se descontó nada de tu plan."
            ),
        )
    db.commit()
