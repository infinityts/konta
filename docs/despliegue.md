# Despliegue de Konta

Guía para correr Konta en local, desplegarla en un servidor y administrarla.

---

## 1. Local (desarrollo)

```bash
# Base de datos
docker compose up -d db

# Backend
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload --port 8000      # API + docs en /docs

# Frontend (otra terminal)
cd frontend
pnpm install
pnpm dev                                        # http://localhost:5173
```

Frontend en `http://localhost:5173` (el proxy de Vite manda `/api` al backend).

---

## 2. Despliegue con Docker / Podman (servidor)

### Opción A — docker compose (recomendado)

```bash
docker compose up -d --build
# Frontend:   http://<host>:8080
# Backend:    http://<host>:8000  (docs en /docs)
# PostgreSQL: <host>:5433
```

### Opción B — Podman directo (sin compose)

Útil cuando el servidor usa Podman y puertos ocupados:

```bash
# Red y volumen persistentes
podman network create konta-net
podman volume create konta-pgdata

# Base de datos
podman run -d --name konta-db --network konta-net --network-alias db \
  -e POSTGRES_USER=finanzas -e POSTGRES_PASSWORD=finanzas -e POSTGRES_DB=finanzas \
  -p 5433:5432 -v konta-pgdata:/var/lib/postgresql/data \
  postgres:16-alpine

# Backend (aplica migraciones y arranca)
podman build -t konta-backend ./backend
podman run -d --name konta-backend --network konta-net --network-alias backend \
  -e FINANZAS_DATABASE_URL=postgresql+psycopg://finanzas:finanzas@db:5432/finanzas \
  -e FINANZAS_SECRET_KEY='un-secreto-largo-y-aleatorio' \
  -e FINANZAS_TIMEZONE=America/Bogota \
  -p 8000:8000 konta-backend

# Frontend (nginx sirve la SPA y hace proxy /api -> backend)
podman build -t konta-frontend ./frontend
podman run -d --name konta-frontend --network konta-net -p 8082:80 konta-frontend
```

> Las `--network-alias db` y `--network-alias backend` son necesarias porque el
> backend se conecta al host `db` y el nginx del frontend hace proxy al host `backend`.

---

## 3. Administración

```bash
podman ps --filter name=konta                              # estado
podman logs -f konta-backend                               # logs de la API
podman logs -f konta-frontend                              # logs de nginx
podman stop konta-frontend konta-backend konta-db          # detener
podman start konta-db konta-backend konta-frontend         # arrancar
podman rm -f konta-backend konta-frontend                  # eliminar contenedores
```

### Actualizar a la última versión

```bash
cd /opt/konta
git fetch --depth 1 origin main && git reset --hard origin/main

podman build -t konta-backend ./backend
podman build -t konta-frontend ./frontend

podman rm -f konta-backend konta-frontend
podman run -d --name konta-backend ...   # (mismos comandos de arriba)
podman run -d --name konta-frontend ...
```

El backend aplica las migraciones pendientes **solo** al arrancar
(`alembic upgrade head`).

---

## 4. Respaldo y restauración de datos

Los datos viven en el volumen `konta-pgdata`.

```bash
# Respaldar
podman exec konta-db pg_dump -U finanzas -d finanzas > respaldo-$(date +%F).sql

# Restaurar (sobre una base vacía)
cat respaldo-2026-09-27.sql | podman exec -i konta-db psql -U finanzas -d finanzas
```

---

## 5. Variables de entorno (backend)

| Variable | Por defecto | Descripción |
|---|---|---|
| `FINANZAS_DATABASE_URL` | `postgresql+psycopg://finanzas:finanzas@localhost:5433/finanzas` | Conexión a PostgreSQL |
| `FINANZAS_SECRET_KEY` | *(placeholder)* | Clave para firmar los JWT (**cámbiala**) |
| `FINANZAS_ACCESS_TOKEN_EXPIRE_MINUTES` | `1440` | Duración del token |
| `FINANZAS_TIMEZONE` | `America/Bogota` | Zona horaria para "hoy" (ingresos recurrentes / alertas) |
| `FINANZAS_SCHEDULER_ENABLED` | `true` | Activa el scheduler: ingresos recurrentes, suscripciones, TRM oficial y notificaciones |

### OCR por línea (opcional)

Tercer nivel del clasificador de artículos de una factura. **Sin** estas variables
la app funciona igual: clasifica con el historial (`reglas_ocr`) y el diccionario.

| Variable | Por defecto | Descripción |
|---|---|---|
| `FINANZAS_OLLAMA_URL` | *(vacío = desactivado)* | Base de Ollama, ej. `http://localhost:11434`. Si no responde, el nivel de embeddings se salta sin fallar la factura |
| `FINANZAS_OLLAMA_EMBEDDING_MODEL` | `nomic-embed-text` | Modelo de embeddings. El perfil de cada etiqueta se cachea en memoria |
| `FINANZAS_OLLAMA_TIMEOUT` | `5.0` | Segundos de espera por llamada |

### Notificaciones (opcionales)

Sin estas variables la app funciona igual; solo el envío de notificaciones avisa
que falta configurarlas.

| Variable | Descripción |
|---|---|
| `FINANZAS_TELEGRAM_BOT_TOKEN` | Token del bot de Telegram (te lo da **@BotFather**). Luego escríbele algo a tu bot y usa el botón **Detectar** en la página de Notificaciones |
| `FINANZAS_SMTP_HOST` | Servidor SMTP (ej. `smtp.gmail.com`) |
| `FINANZAS_SMTP_PORT` | Puerto SMTP (por defecto `587`) |
| `FINANZAS_SMTP_USER` | Usuario SMTP |
| `FINANZAS_SMTP_PASSWORD` | Contraseña o *app password* |
| `FINANZAS_SMTP_FROM` | Remitente (por defecto, el usuario SMTP) |
| `FINANZAS_SMTP_TLS` | `true` para STARTTLS (por defecto) |
| `FINANZAS_WHATSAPP_TOKEN` | Token de la **Cloud API** de Meta (permanente, de un usuario del sistema) |
| `FINANZAS_WHATSAPP_PHONE_ID` | *Phone number ID* del número emisor en Meta |
| `FINANZAS_WHATSAPP_API_VERSION` | `v21.0` — versión de Graph API |

> **WhatsApp tiene una condición extra**: fuera de la ventana de 24 h desde el último
> mensaje del usuario, Meta rechaza el texto libre y exige una **plantilla aprobada**
> (categoría *utility*). Para el resumen diario hay que crear y aprobar la plantilla en
> Meta Business y usarla; sin ella el envío devuelve el error de Meta tal cual.

Ejemplo para agregarlas al contenedor:

```bash
podman run -d --name konta-backend ... \
  -e FINANZAS_TELEGRAM_BOT_TOKEN='123456:ABC...' \
  -e FINANZAS_SMTP_HOST='smtp.gmail.com' \
  -e FINANZAS_SMTP_USER='tu@gmail.com' \
  -e FINANZAS_SMTP_PASSWORD='app-password' \
  -e FINANZAS_SMTP_FROM='tu@gmail.com' \
  konta-backend
```

---

## 6. Frontend

| Variable | Por defecto | Descripción |
|---|---|---|
| `VITE_API_URL` | `/api` | Base de la API (por defecto se usa el proxy) |
