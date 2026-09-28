# Konta — finanzas personales

App de finanzas personales: suscripciones, tarjetas de crédito, gastos/ingresos,
reportes y más. **Multi-usuario y multi-moneda**, con datos 100% locales.

## Stack

- **Backend**: FastAPI + SQLAlchemy + Alembic + PostgreSQL
- **Frontend** (próximamente): React + Vite + TypeScript + Tailwind + shadcn/ui
- **Futuro**: OCR de facturas PDF, tasas de interés de tarjetas, comparativo de
  mercado, alarmas de pagos.

## Requisitos

- Docker + Docker Compose
- Python ≥ 3.11

## Inicio rápido

```bash
# 1. Base de datos (PostgreSQL 16, puerto 5433)
docker compose up -d db

# 2. Backend
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# 3. Migraciones
cp .env.example .env   # ajusta si hace falta
alembic upgrade head

# 4. Arrancar la API
uvicorn app.main:app --reload --port 8000
```

API en `http://localhost:8000` (docs en `/docs`).

## Endpoints (todos protegidos con Bearer token, aislados por usuario)

| Recurso | Endpoints |
|---|---|
| Auth | `POST /auth/register`, `POST /auth/login` |
| Categorías | `GET/POST /categorias`, `GET/PATCH/DELETE /categorias/{id}` |
| Tarjetas | `GET/POST /tarjetas`, `GET/PATCH/DELETE /tarjetas/{id}` |
| Suscripciones | `GET/POST /suscripciones`, `GET/PATCH/DELETE /suscripciones/{id}` |
| Transacciones | `GET/POST /transacciones`, `GET/PATCH/DELETE /transacciones/{id}` |

## Modelo de datos (núcleo)

`usuarios`, `monedas`, `tasas_cambio`, `categorias`, `tarjetas`,
`suscripciones`, `transacciones` — migrado con Alembic (`alembic/versions/`).

## Tests

```bash
cd backend
# con la base de datos arriba:
FINANZAS_TEST_DATABASE_URL=postgresql+psycopg://finanzas:finanzas@localhost:5433/finanzas pytest
```

## Estado

- [x] Backend: auth multi-usuario + CRUD core (verificado contra PostgreSQL)
- [ ] Frontend React
- [ ] Reportes/dashboard, alarmas, OCR, mercado, tasas
