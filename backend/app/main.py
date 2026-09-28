"""Punto de entrada de la API de Konta."""

from fastapi import FastAPI

from .routers import auth, categorias, suscripciones, tarjetas, transacciones

app = FastAPI(title="Konta API", version="0.1.0")

app.include_router(auth.router)
app.include_router(categorias.router)
app.include_router(tarjetas.router)
app.include_router(suscripciones.router)
app.include_router(transacciones.router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "app": "konta"}
