"""El asistente dentro de la app: se pregunta y responde con las reglas de Konta."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import asistente, cuotas, ia, manual
from ..deps import get_current_user, get_db
from ..models import Usuario
from ..schemas import PreguntaAsistenteIn, RespuestaAsistenteOut

router = APIRouter(prefix="/asistente", tags=["asistente"])

# Preguntas de ejemplo, para que la pantalla tenga por dónde empezar
SUGERENCIAS = [
    "¿Cómo voy este mes?",
    "¿Cuánto gasté en mercado?",
    "¿Por qué cambió mi saldo?",
    "¿Cómo subo una factura?",
    "¿Cuánto debo en mis tarjetas?",
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
        consultas_restantes=cuota["consultas"]["restantes"],
        tokens_entrada=resultado["tokens_entrada"],
        tokens_salida=resultado["tokens_salida"],
        costo_usd=resultado["costo_usd"],
    )
