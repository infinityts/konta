# Konta — Finanzas personales

App de finanzas personales **multi-usuario** y **multi-moneda**: suscripciones,
tarjetas de crédito, ingresos (fijos y recurrentes), gastos, etiquetas, reportes,
alarmas de pagos y OCR de facturas. **Datos 100% locales.**

---

## Funcionalidades

### Cuentas y accesos
- Registro y login con **JWT** (contraseñas con **bcrypt**).
- **Aislamiento total por usuario**: cada persona ve solo sus datos.
- Al registrarse se crean **categorías por defecto** (gastos e ingresos).

### Ingresos
- **Transacciones de ingreso** con descripción (salario, freelance, extras).
- **Ingresos recurrentes** con periodicidad **diaria, semanal o mensual**:
  marcas el día y un **scheduler** registra el ingreso **automáticamente** cuando
  corresponde (y hace *catch-up* si la app estaba apagada).

### Gastos, tarjetas y suscripciones
- **Tarjetas** de crédito/débito (banco, día de corte, día de pago, límite, tasa).
- **Suscripciones** (monto, moneda, periodicidad, próximo pago, tarjeta y categoría).
- **Transacciones** de gasto/ingreso con categoría, tarjeta y suscripción.
- **Simulador de intereses**: con la tasa **mensual** de la tarjeta, calcula cuántos meses
  tardas en pagar una deuda y cuánto pagas de intereses; avisa si el pago no cubre el interés.

### Organización
- **Etiquetas y subetiquetas** jerárquicas (autojerárquicas) asociadas a transacciones.

### Análisis
- **Dashboard**: balance del mes (ingresos vs gastos), top categorías, próximos pagos.
- **Reportes**: evolución mensual (últimos 6 meses) y desglose por categoría.
- **Alertas de pagos**: próximos vencimientos de suscripciones y de tarjetas (pago/corte).
- **Presupuestos**: límite mensual por categoría, con gasto real, % consumido y aviso de exceso.

### Documentos
- **Facturas PDF**: subida, extracción de texto (**pypdf** + **OCR tesseract** en
  español) y detección heurística de **monto** y **fecha**; asociación a transacciones.

### Datos
- **Importar estado de cuenta (CSV)**: sube el CSV del banco; detecta las columnas de
  fecha, descripción y monto, y muestra una **previsualización** antes de crear las
  transacciones.

### Mercado
- **Lista de compras**: items a comprar con cantidad y precio estimado, total estimado
  y marcado de "comprado".
- **Comparativo de precios**: registra precios por **producto y tienda** (histórico) y
  muestra cuál tienda es **más barata**.

### Multi-moneda
- **Tasas de cambio**: registro manual o **descarga desde internet**
  (API pública `open.er-api.com`), con histórico por fecha.
- **Conversor** entre monedas y catálogo de monedas disponibles (COP, USD, EUR, MXN,
  PEN, CLP, ARS, UYU, BRL, GBP).

### Respaldo
- **Exportar**: respaldo completo en **JSON** y transacciones en **CSV**.
- **Restaurar**: recupera todos tus datos desde un respaldo JSON (reemplaza lo actual).
- A nivel de servidor también se puede respaldar la base con `pg_dump`
  (ver [`docs/despliegue.md`](docs/despliegue.md)).

---

## Stack

| Capa | Tecnología |
|---|---|
| Backend | FastAPI + SQLAlchemy + Alembic |
| Base de datos | PostgreSQL 16 |
| Frontend | React + Vite + TypeScript + Tailwind CSS |
| Scheduler | APScheduler (ingresos recurrentes) |
| OCR | pypdf + tesseract-ocr |
| Despliegue | Docker / Podman (compose) |

```
[ Navegador ]  React (Vite) ──/api/*──►  nginx
                                            │ proxy
                                            ▼
                                  FastAPI (+ scheduler) ──► PostgreSQL
```

---

## Inicio rápido (local)

```bash
# 1. Base de datos (PostgreSQL 16 en el puerto 5433)
docker compose up -d db

# 2. Backend
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload --port 8000      # API + docs en /docs

# 3. Frontend (otra terminal)
cd frontend
pnpm install
pnpm dev                                        # http://localhost:5173
```

## Despliegue con Docker / Podman

```bash
docker compose up -d --build
# Frontend:  http://localhost:8080
# Backend:   http://localhost:8000  (docs en /docs)
# PostgreSQL: localhost:5433
```

➡️ Guía completa (local, servidor con Podman, administración, respaldo y variables
de entorno) en [`docs/despliegue.md`](docs/despliegue.md).

---

## Endpoints

Todos (salvo `register`/`login`) requieren `Authorization: Bearer <token>` y están
aislados por usuario.

| Recurso | Endpoints |
|---|---|
| **Auth** | `POST /auth/register`, `POST /auth/login`, `GET /auth/me` |
| **Categorías** | `GET/POST /categorias`, `GET/PATCH/DELETE /categorias/{id}` |
| **Tarjetas** | `GET/POST /tarjetas`, `GET/PATCH/DELETE /tarjetas/{id}`, `GET /tarjetas/{id}/simulador` |
| **Suscripciones** | `GET/POST /suscripciones`, `GET/PATCH/DELETE /suscripciones/{id}` |
| **Transacciones** | `GET/POST /transacciones`, `GET/PATCH/DELETE /transacciones/{id}` |
| **Ingresos recurrentes** | `GET/POST /ingresos-recurrentes`, `GET/PATCH/DELETE /ingresos-recurrentes/{id}` |
| **Etiquetas** | `GET/POST /etiquetas`, `GET/PATCH/DELETE /etiquetas/{id}` |
| **Alertas** | `GET /alertas?dias=15` |
| **Reportes** | `GET /reportes/mensual?meses=6`, `GET /reportes/categorias?mes=YYYY-MM` |
| **Facturas** | `GET/POST /facturas`, `POST /facturas/{id}/asociar`, `DELETE /facturas/{id}` |
| **Presupuestos** | `GET/POST /presupuestos`, `PATCH/DELETE /presupuestos/{id}` |
| **Importar** | `POST /importar/csv` (previsualizar), `POST /importar/confirmar` |
| **Mercado** | `GET/POST /productos`, `GET/PATCH/DELETE /productos/{id}`, `GET /productos/{id}/comparativo`, `GET/POST /productos/{id}/precios` |
| **Lista de compras** | `GET/POST /lista-mercado`, `PATCH/DELETE /lista-mercado/{id}` |
| **Monedas / tasas** | `GET /monedas`, `GET/POST /tasas`, `DELETE /tasas/{id}`, `POST /tasas/actualizar`, `GET /convertir?de=&a=&monto=` |
| **Respaldo** | `GET /exportar/json`, `GET /exportar/transacciones.csv`, `POST /respaldar/restaurar` |

---

## Modelo de datos

Migrado con **Alembic** (`backend/alembic/versions/`):

| Migración | Contenido |
|---|---|
| `0001_nucleo` | `usuarios`, `monedas`, `tasas_cambio`, `categorias`, `tarjetas`, `suscripciones`, `transacciones` |
| `0002_ingresos_recurrentes` | `ingresos_recurrentes` |
| `0003_etiquetas` | `etiquetas` (autojerárquica) + `transacciones.etiqueta_id` |
| `0004_facturas` | `facturas` |
| `0005_presupuestos` | `presupuestos` |
| `0006_mercado` | `productos`, `precios_mercado`, `lista_mercado` |

---

## Tests

```bash
cd backend
# con la base de datos arriba:
FINANZAS_TEST_DATABASE_URL=postgresql+psycopg://finanzas:finanzas@localhost:5433/finanzas pytest
```

Cobertura: auth, CRUD core, aislamiento multi-usuario, ingresos recurrentes,
etiquetas/subetiquetas (con cascada), alertas de pagos, reportes y facturas (OCR).

---

## Estado

- [x] Backend: auth multi-usuario + CRUD + ingresos recurrentes + etiquetas + alertas + reportes + facturas OCR + presupuestos + importar CSV + mercado + multi-moneda + simulador de intereses + respaldo
- [x] Frontend: login/registro, dashboard, CRUD, ingresos recurrentes, reportes, etiquetas, facturas, presupuestos, importar, mercado, monedas, respaldo
- [x] Despliegue con Docker/Podman
- [ ] Proyección de flujo de caja, metas de ahorro
- [ ] Notificaciones de alarmas por email/Telegram
