# Konta — Finanzas personales

[![CI](https://github.com/infinityts/konta/actions/workflows/ci.yml/badge.svg)](https://github.com/infinityts/konta/actions/workflows/ci.yml)

App de finanzas personales **multi-usuario** y **multi-moneda**: suscripciones,
tarjetas de crédito, ingresos (fijos y recurrentes), gastos, etiquetas, reportes,
alarmas de pagos y OCR de facturas. **Datos 100% locales.**

---

## Documentación

| Documento | Contenido |
|---|---|
| [`README.md`](README.md) | Funcionalidades, stack, endpoints y modelo de datos (este archivo) |
| [`docs/guia-uso.md`](docs/guia-uso.md) | **Guía práctica de uso**: cuentas, categorías vs etiquetas, tarjetas y errores comunes |
| [`docs/arquitectura.md`](docs/arquitectura.md) | Arquitectura, módulos, scheduler, notificaciones y relaciones |
| [`docs/despliegue.md`](docs/despliegue.md) | Local, Docker/Podman, administración, respaldo y variables de entorno |
| [`CHANGELOG.md`](CHANGELOG.md) | Historial de cambios commit por commit |

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
- **Tarjetas** de crédito/débito (banco, día de corte, día de pago, **cupo total**, tasa).
  Las de **débito** se **asocian a su cuenta** (son un instrumento de esa cuenta, no un saldo
  aparte); las de **crédito** son un pasivo y no tocan las cuentas.
  La tasa se toma del extracto como **E.A. (efectiva anual)** y la app la convierte a la
  mensual real (`(1+EA)^(1/12)−1`), que es la que usa el simulador.
- **Deuda de la tarjeta** por moneda — lo que dice el extracto (ej. `COP 8.912.816` + `USD 700`),
  con **total en COP** cuando hay tasa de cambio registrada.
- **Suscripciones** (monto, moneda, periodicidad, próximo pago, tarjeta y categoría).
- **Transacciones** de gasto/ingreso con categoría, tarjeta y suscripción.
- **Simulador de intereses**: con la tasa **mensual** de la tarjeta, calcula cuántos meses
  tardas en pagar una deuda y cuánto pagas de intereses; avisa si el pago no cubre el interés.
  Si no indicas saldo, usa la **deuda registrada** de la tarjeta.

### Seguros y pólizas
- **Pólizas de vida, salud, vehículo u hogar** para personas y/o bienes: aseguradora,
  número de póliza, **asegurado** (persona) o **bien asegurado** (vehículo con **placa**,
  marca, modelo y **valor asegurado**).
- **Varias personas cubiertas** por póliza (una póliza familiar): nombre, parentesco y fecha
  de nacimiento, con un **titular** (solo uno: al marcar otro, el anterior deja de serlo).
  El *asegurado principal* de la póliza se conserva para el título.
- **Prima** con su moneda y periodicidad (mensual, trimestral, semestral o anual): al
  vencer, un job genera **automáticamente el gasto**, heredando categoría, etiqueta,
  tarjeta y cuenta — igual que las suscripciones, e **idempotente**.
- **Vigencia** (inicio y fin) y **renovación automática**; las alertas avisan de la
  **prima próxima** y del **vencimiento de la vigencia** (salvo si renueva sola).
- **Beneficiarios** con parentesco y **porcentaje** (no pueden sumar más de 100).
- **Costo anual de seguros**: prima mensual y anual normalizada a COP.
- Las primas entran en el **gasto fijo** del diagnóstico del dashboard.

### Organización
- **Un solo árbol `Categoría › Etiqueta › Subetiqueta`**: la categoría es el contexto
  (Vivienda, Transporte, Casa 1…) y el anidamiento vive en las etiquetas. El dashboard y
  los reportes agrupan por esa ruta, y los nombres son **únicos entre hermanos** (sin
  distinguir mayúsculas).
- **Editar** categorías y etiquetas, y **crear etiquetas en línea** desde el propio
  movimiento.

### Análisis
- **Dashboard**: **saldo actual** (con el motivo si estás sobregirado), balance del mes,
  top categorías, próximos pagos.
- **Reportes**: evolución mensual (últimos 6 meses), desglose por categoría y **costo de los
  seguros** (prima mensual y anual, con desglose por tipo).
- **Alertas de pagos**: próximos vencimientos de suscripciones y de tarjetas (pago/corte).
- **Presupuestos**: límite mensual por categoría, con gasto real, % consumido y aviso de exceso.
- **Flujo de caja**: proyección a 3/6/12 meses combinando ingresos recurrentes, **cobros
  fijos** (suscripciones **y pólizas de seguro**, cada una en los meses en que toca pagar:
  una prima semestral aparece cada 6 meses, no todos) y el gasto variable promedio; muestra
  balance y acumulado. **Todo en COP**: lo que esté en otra moneda se convierte con la tasa
  registrada, y si falta la tasa se avisa en vez de sumar el número en crudo.

### Saldo y consolidado
- **Cuentas** (efectivo, banco, ahorros…) cada una con su **saldo inicial**; el
  **saldo actual** = `saldo inicial + ingresos − gastos`, por cuenta y total.
- **Consolidado mes a mes** con saldo inicial, ingresos, gastos, balance y
  **saldo final corrido**.
- **Diagnóstico del saldo**: si estás **sobregirado** te dice **por qué** — qué
  categorías pesan más, cuánto son los gastos fijos (suscripciones), cómo vas frente
  al mes anterior y cuánto aportaron los ingresos.

### Ahorro
- **Metas de ahorro**: objetivo, **aportes**, progreso (%) y **aporte mensual sugerido**
  según la fecha límite.

### Documentos
- **Facturas PDF o foto del recibo**: subida, extracción de texto (**pypdf** + **OCR
  tesseract** en español, con preprocesado para fotos de recibos arrugados) y detección
  heurística de **monto** y **fecha**; asociación a transacciones.
- **OCR por línea**: un recibo de mercado o de gasolina no es un gasto único, son N
  artículos. La app parte el texto en líneas (`lineas.py`), entiende el formato de dinero
  colombiano (`15.916` son quince mil novecientos dieciséis) y clasifica cada artículo
  contra tu árbol de etiquetas en cascada:
  **historial** (lo que ya corregiste) → **diccionario** (palabras típicas de un recibo) →
  **embeddings** (similitud semántica vía Ollama, opcional). Lo que no sabe decidir queda
  *sin clasificar* para que lo elijas una vez — y a la próxima ya lo sabe.
  Al confirmar, **cada línea crea su propia transacción** con su categoría y etiqueta.

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

### Notificaciones
- **Resumen diario de pagos** por **Telegram**, **correo** (SMTP) y/o **WhatsApp**
  (Cloud API de Meta), con días de anticipación configurables. Se envía **como máximo
  una vez al día**.
- La config del servidor (token del bot, SMTP y credenciales de Meta) es global; cada
  usuario elige canal, destino y días. Incluye botón de **prueba** y **detección del
  chat ID** de Telegram.
- *Nota sobre WhatsApp*: fuera de la ventana de 24 h desde el último mensaje del
  usuario, Meta exige una **plantilla aprobada** (*utility*); un texto libre se
  rechaza. La app envía texto y avisa con el error de Meta si falta la plantilla.

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
| **Categorías** | `GET/POST /categorias`, `GET/PATCH/DELETE /categorias/{id}`, `GET /categorias/arbol` |
| **Tarjetas** | `GET/POST /tarjetas`, `GET/PATCH/DELETE /tarjetas/{id}`, `GET/POST /tarjetas/{id}/deudas`, `DELETE /tarjetas/{id}/deudas/{deuda_id}`, `GET /tarjetas/{id}/simulador` |
| **Suscripciones** | `GET/POST /suscripciones`, `GET/PATCH/DELETE /suscripciones/{id}` |
| **Pólizas** | `GET/POST /polizas`, `GET/PATCH/DELETE /polizas/{id}`, `GET /polizas/resumen`, `POST /polizas/{id}/asegurados`, `PATCH/DELETE /polizas/asegurados/{asegurado_id}`, `POST /polizas/{id}/beneficiarios`, `PATCH/DELETE /polizas/beneficiarios/{beneficiario_id}` |
| **Transacciones** | `GET/POST /transacciones`, `GET/PATCH/DELETE /transacciones/{id}` |
| **Ingresos recurrentes** | `GET/POST /ingresos-recurrentes`, `GET/PATCH/DELETE /ingresos-recurrentes/{id}` |
| **Etiquetas** | `GET/POST /etiquetas`, `GET/PATCH/DELETE /etiquetas/{id}` |
| **Alertas** | `GET /alertas?dias=15` |
| **Reportes** | `GET /reportes/mensual?meses=6`, `GET /reportes/categorias?mes=YYYY-MM`, `GET /reportes/seguros` |
| **Facturas** | `GET/POST /facturas`, `GET/DELETE /facturas/{id}`, `POST /facturas/{id}/asociar`, `POST /facturas/{id}/lineas`, `PATCH/DELETE /facturas/{id}/lineas/{linea_id}`, `POST /facturas/{id}/confirmar` |
| **Presupuestos** | `GET/POST /presupuestos`, `PATCH/DELETE /presupuestos/{id}` |
| **Importar** | `POST /importar/csv` (previsualizar), `POST /importar/confirmar` |
| **Mercado** | `GET/POST /productos`, `GET/PATCH/DELETE /productos/{id}`, `GET /productos/{id}/comparativo`, `GET/POST /productos/{id}/precios` |
| **Lista de compras** | `GET/POST /lista-mercado`, `PATCH/DELETE /lista-mercado/{id}` |
| **Monedas / tasas** | `GET /monedas`, `GET/POST /tasas`, `DELETE /tasas/{id}`, `POST /tasas/actualizar`, `GET /convertir?de=&a=&monto=` |
| **Respaldo** | `GET /exportar/json`, `GET /exportar/transacciones.csv`, `POST /respaldar/restaurar` |
| **Flujo de caja** | `GET /flujo-caja?meses=6` |
| **Metas de ahorro** | `GET/POST /metas`, `PATCH/DELETE /metas/{id}`, `GET/POST /metas/{id}/aportes`, `DELETE /metas/aportes/{aporte_id}` |
| **Notificaciones** | `GET/PUT /notificaciones`, `POST /notificaciones/probar`, `POST /notificaciones/telegram/detectar` |
| **Cuentas** | `GET/POST /cuentas`, `PATCH/DELETE /cuentas/{id}`, `POST /cuentas/{id}/adoptar-movimientos` |
| **Saldos** | `GET /saldos`, `GET /saldos/consolidado?meses=6`, `GET /saldos/diagnostico` |
| **Salud** | `GET /health` (sin token) |

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
| `0007_metas_ahorro` | `metas_ahorro`, `aportes_meta` |
| `0008_notificaciones` | `config_notificaciones` |
| `0009_cuentas_jerarquia` | `cuentas` + `transacciones.cuenta_id` + `categorias.padre_id` |
| `0010_deudas_tarjeta` | `deudas_tarjeta` |
| `0011_tasa_ea` | `tarjetas.tasa_interes_ea` (E.A. del extracto) |
| `0012_tarjeta_cuenta` | `tarjetas.cuenta_id` (débito → su cuenta) |
| `0013_etiquetas_en_categorias` | `etiquetas.categoria_id` + unicidad entre hermanos |
| `0014_arbol_unico` | migra subcategorías a etiquetas y elimina `categorias.padre_id` |
| `0015_suscripcion_etiqueta` | `suscripciones.etiqueta_id` |
| `0016_ocr_lineas` | `factura_lineas`, `reglas_ocr` (OCR por línea) |
| `0017_nombres_indices_orm` | renombra los índices al nombre que espera el ORM (`alembic check` limpio) |
| `0018_whatsapp` | `config_notificaciones.whatsapp_numero` (canal WhatsApp) |
| `0019_polizas` | `polizas`, `beneficiarios` + `transacciones.poliza_id` + periodicidad `semestral` |
| `0020_poliza_asegurados` | `poliza_asegurados` (varias personas cubiertas por póliza) |
| `0021_uq_categorias_raiz` | recupera la unicidad de categorías por usuario (la 0014 se llevó el índice) y fusiona duplicados |

---

## Tests

```bash
cd backend
# con la base de datos arriba:
FINANZAS_TEST_DATABASE_URL=postgresql+psycopg://finanzas:finanzas@localhost:5433/finanzas pytest
```

Cobertura: auth, CRUD core, aislamiento multi-usuario, ingresos recurrentes,
suscripciones que generan su gasto, pólizas (generación del gasto, beneficiarios y
alertas de vigencia), etiquetas/subetiquetas (con cascada y unicidad
entre hermanos), alertas de pagos, reportes, facturas (OCR y OCR por línea con
clasificación y aprendizaje), presupuestos, importar
CSV, mercado, multi-moneda, simulador y deuda de tarjeta, respaldo, flujo de caja,
migraciones **con datos** (no solo con tablas vacías),
metas de ahorro, notificaciones, cuentas/saldos y diagnóstico del sobregiro.

**48 tests en verde.** El esquema se mantiene alineado con el ORM:
`alembic check` no reporta operaciones pendientes.

---

## Estado

- [x] Backend: auth multi-usuario + CRUD + ingresos recurrentes + suscripciones que generan su gasto + **pólizas de seguro** (prima que genera su gasto, vigencia, vencimiento y beneficiarios) + árbol Categoría › Etiqueta › Subetiqueta + alertas + reportes + facturas con OCR por línea (clasificación en cascada y aprendizaje) + presupuestos + importar CSV + mercado + multi-moneda (TRM oficial) + simulador y deuda de tarjeta + respaldo + flujo de caja + metas de ahorro + notificaciones (Telegram, correo y WhatsApp) + cuentas/saldos
- [x] Frontend: login/registro, dashboard con KPIs y motivo del sobregiro, cuentas y consolidado, categorías y etiquetas, transacciones con **edición** y etiquetas, tarjetas con deuda, edición y simulador, suscripciones con edición y pausa, seguros con beneficiarios y costo anual, ingresos recurrentes, reportes, facturas con líneas OCR editables, presupuestos, importar, mercado, monedas, respaldo, flujo de caja, metas, notificaciones
- [x] Navegación agrupada: `Resumen` + 5 grupos en barra superior (hover en escritorio, hamburguesa en móvil), definidos en `frontend/src/nav.ts`
- [x] Loader `AccordionLoader` (alias `@` → `src`) y **carga diferida por página** (bundle inicial 271 kB → 183 kB)
- [x] Despliegue con Docker/Podman
- [x] Esquema sin deriva: `alembic check` limpio y `downgrade base` → `upgrade head` sin errores
- [x] **OCR por línea**: `factura_lineas` + `reglas_ocr` expuestos en la API y en la UI de *Facturas*
- [x] CI: `pytest` (con PostgreSQL 16 y `alembic check`) + `pnpm build` en GitHub Actions
- [x] **WhatsApp** como canal de notificaciones (Cloud API de Meta; requiere plantilla *utility* aprobada para el envío diario)
- [x] **Seguros y pólizas** (vida/salud/vehículo/hogar): prima que genera su gasto, vigencia y vencimiento, **varias personas cubiertas**, beneficiarios con porcentaje y bien asegurado (placa)
- [x] **Costo anual de los seguros** en *Reportes* (con desglose por tipo) y en el gasto fijo del dashboard
- [x] **Flujo de caja** en COP: convierte lo que esté en otra moneda, avisa si falta la tasa, e incluye las pólizas con su periodicidad real
