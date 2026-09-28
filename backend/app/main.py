"""Punto de entrada de la API de Konta."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import auth, categorias, suscripciones, tarjetas, transacciones

app = FastAPI(title="Konta API", version="0.1.0")

# CORS para el frontend (Vite dev en :5173)
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


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "app": "konta"}
