"""Punto de entrada de la API de Konta."""

import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from .config import get_settings
from .deps import get_db
from .recurrencia import procesar_ingresos_vencidos
from .routers import (
    alertas,
    auth,
    categorias,
    cuentas,
    etiquetas,
    facturas,
    flujo,
    importacion,
    ingresos_recurrentes,
    lista_mercado,
    metas,
    monedas,
    notificaciones,
    polizas,
    presupuestos,
    productos,
    reportes,
    respaldo,
    saldos,
    suscripciones,
    tarjetas,
    transacciones,
)
from .scheduler import start_scheduler, stop_scheduler
from .schemas import SaludOut

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if get_settings().scheduler_enabled:
        start_scheduler()
        try:
            # catch-up al arrancar (ingresos vencidos mientras el app estaba apagada)
            procesar_ingresos_vencidos()
        except Exception:
            pass
    yield
    if get_settings().scheduler_enabled:
        stop_scheduler()


app = FastAPI(title="Konta API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(categorias.router)
app.include_router(tarjetas.router)
app.include_router(suscripciones.router)
app.include_router(transacciones.router)
app.include_router(ingresos_recurrentes.router)
app.include_router(etiquetas.router)
app.include_router(alertas.router)
app.include_router(reportes.router)
app.include_router(facturas.router)
app.include_router(presupuestos.router)
app.include_router(importacion.router)
app.include_router(productos.router)
app.include_router(lista_mercado.router)
app.include_router(monedas.router)
app.include_router(respaldo.router)
app.include_router(flujo.router)
app.include_router(metas.router)
app.include_router(notificaciones.router)
app.include_router(polizas.router)
app.include_router(cuentas.router)
app.include_router(saldos.router)


@app.get("/health", response_model=SaludOut, responses={503: {"model": SaludOut}})
def health(db: Session = Depends(get_db)):
    """Estado del servicio **y de la base de datos**.

    Responde `503` si la base no contesta: es lo que hace que el healthcheck del
    contenedor sirva de algo (antes respondía `ok` aunque PostgreSQL estuviera
    caído, así que un despliegue roto se veía verde). No pide token —lo consulta el
    orquestador— y no filtra la cadena de conexión, solo el tipo de error.
    """
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:  # cualquier fallo aquí significa «no puedo servir»
        logger.warning("health: la base de datos no responde (%s)", exc)
        return JSONResponse(
            status_code=503,
            content={
                "status": "error",
                "app": "konta",
                "base": "sin conexión",
                "error": type(exc).__name__,
            },
        )
    return {"status": "ok", "app": "konta", "base": "ok"}
