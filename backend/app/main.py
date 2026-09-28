"""Punto de entrada de la API de Konta."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .recurrencia import procesar_ingresos_vencidos
from .routers import (
    alertas,
    auth,
    categorias,
    etiquetas,
    facturas,
    importacion,
    ingresos_recurrentes,
    lista_mercado,
    monedas,
    presupuestos,
    productos,
    reportes,
    suscripciones,
    tarjetas,
    transacciones,
)
from .scheduler import start_scheduler, stop_scheduler


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


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "app": "konta"}
