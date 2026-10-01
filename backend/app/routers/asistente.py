"""El asistente dentro de la app: se pregunta y responde con las reglas de Konta."""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import asistente, cuotas, ia, manual, propuestas
from ..deps import get_current_user, get_db
from ..models import Usuario
from ..schemas import (
    PreguntaAsistenteIn,
    PropuestaOut,
    RespuestaAsistenteOut,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/asistente", tags=["asistente"])

# Preguntas de ejemplo, para que la pantalla tenga por dónde empezar
SUGERENCIAS = [
    "¿Cómo voy este mes?",
    "Compárame este mes con el anterior",
    "¿En qué se me fue la plata en mercado?",
    "¿Qué productos me están subiendo el mercado?",
    "¿Por qué cambió mi saldo?",
    "¿Cuánto debo en mis tarjetas?",
    "¿Cómo subo una factura?",
    "¿Cómo separo los gastos de casa y apartamento?",
]


@router.get("/sugerencias")
def sugerencias():
    """Preguntas de ejemplo para arrancar la conversación."""
    return {"sugerencias": SUGERENCIAS}


@router.get("/manual")
def ver_manual():
    """Los temas que el asistente sabe explicar paso a paso."""
    return {"temas": manual.temas(), "cuantos": len(manual.temas())}


@router.get("/buscar")
def buscar_en_la_ayuda(q: str, user: Usuario = Depends(get_current_user)):
    """Qué temas responden a una pregunta y con qué similitud.

    Es la misma búsqueda que usa el asistente por dentro: sirve para ver por qué respondió lo que
    respondió (y para comprobar que encuentra por significado y no por palabras).
    """
    return manual.buscar(q)


@router.get("/propuestas", response_model=list[PropuestaOut])
def listar_propuestas(db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    """Lo que el asistente propuso y está esperando tu confirmación."""
    return propuestas.pendientes(db, user)


@router.post("/propuestas/{propuesta_id}/confirmar")
def confirmar_propuesta(
    propuesta_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """Ejecuta lo propuesto. Solo lo hace si el usuario lo confirma, y solo una vez."""
    propuesta, resultado, nuevo = propuestas.confirmar(db, user, propuesta_id)
    return {
        "estado": propuesta.estado,
        "resultado": resultado,
        "ejecutado_ahora": nuevo,
        "resumen": propuesta.resumen,
    }


@router.post("/propuestas/{propuesta_id}/rechazar", response_model=PropuestaOut)
def rechazar_propuesta(
    propuesta_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """Descarta lo propuesto: no se ejecuta nada."""
    return propuestas.rechazar(db, user, propuesta_id)


@router.post("/preguntar", response_model=RespuestaAsistenteOut)
def preguntar(
    data: PreguntaAsistenteIn,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """Responde una pregunta sobre la app o sobre las finanzas del usuario.

    Cuesta una consulta del plan. El cupo se comprueba **antes** de llamar al modelo: si no hay,
    no se gasta nada. La respuesta dice qué herramientas se usaron, para poder comprobarla.
    """
    pregunta = (data.pregunta or "").strip()
    if len(pregunta) < 3:
        raise HTTPException(status_code=400, detail="Escribe una pregunta.")
    try:
        resultado = asistente.preguntar(db, user, pregunta)
    except HTTPException:
        # El cupo agotado (402) y cualquier otro aviso de la app tienen que llegar tal cual:
        # antes el except genérico los convertía en un 502 que no explicaba nada.
        raise
    except ia.IaNoConfigurada as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except Exception as error:
        logger.exception("El asistente falló respondiendo «%s»", peticion.pregunta[:80])
        raise HTTPException(
            status_code=502,
            detail=(
                "No pude consultar al asistente; no se descontó ninguna consulta de tu plan. "
                f"({type(error).__name__})"
            ),
        ) from error
    cuota = cuotas.resumen(db, user)
    return RespuestaAsistenteOut(
        respuesta=resultado["respuesta"],
        herramientas_usadas=resultado["herramientas_usadas"],
        propuestas=resultado.get("propuestas", []),
        consultas_restantes=cuota["consultas"]["restantes"],
        tokens_entrada=resultado["tokens_entrada"],
        tokens_salida=resultado["tokens_salida"],
        costo_usd=resultado["costo_usd"],
    )
