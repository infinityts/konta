# Arquitectura de Konta

Documento técnico: cómo está construido Konta, qué decisiones se tomaron y cómo se
relacionan las piezas.

---

## Visión general

```
┌────────────┐   /api/*    ┌──────────────┐   SQL    ┌──────────────┐
│  Navegador │────────────▶│    nginx     │─────────▶│  PostgreSQL  │
│  (React)   │             │  (frontend)  │          │     16       │
└────────────┘             └──────┬───────┘          └──────────────┘
                                  │ proxy                    ▲
                                  ▼                          │
                           ┌──────────────┐                  │
                           │   FastAPI    │──────────────────┘
                           │  + scheduler │
                           └──────┬───────┘
                                  │
                    ┌─────────────┴─────────────┐
                    ▼                           ▼
            Telegram Bot API              SMTP (correo)
```

- **Un solo backend** sirve la API y ejecuta el scheduler en segundo plano.
- **El frontend** es una SPA; nginx sirve los estáticos y hace de proxy de `/api`
  hacia el backend (así no hay problemas de CORS en producción).
- **API-first**: todo se hace vía REST, para que una app móvil pueda consumir lo mismo.

---

## Stack y decisiones

| Decisión | Por qué |
|---|---|
| **PostgreSQL** | Tipos ricos (UUID, NUMERIC, ENUM), fechas y agregaciones potentes |
| **SQLAlchemy 2.0 (estilo `Mapped`)** | Tipado estático + sesiones explícitas |
| **Alembic** | El esquema **solo** evoluciona por migraciones; nunca a mano |
| **UUID** como PK | IDs no adivinables; el cliente puede generarlos |
| **`NUMERIC(14,2)`** para dinero | Nunca `float` para montos |
| **ENUM de PostgreSQL** | Vocabulario cerrado a nivel de base de datos |
| **JWT (HS256)** | API sin estado, apta para móvil |
| **bcrypt** para contraseñas | Estándar, con sal |
| **APScheduler** en el proceso | Un solo contenedor; sin necesidad de Celery/Redis |
| **Tailwind v4** | UI simple sin CSS a mano |

---

## Multi-usuario (aislamiento)

- Todas las entidades de negocio tienen `usuario_id` con `ON DELETE CASCADE`.
- El token JWT identifica al usuario (`get_current_user`).
- Cada lectura/escritura pasa por `get_owned(...)`, que devuelve **404** si el
  recurso no existe **o es de otro usuario** (no filtra información).
- `monedas` y `tasas_cambio` son **globales** (son datos objetivos, no del usuario);
  `config_notificaciones` es una fila por usuario.

---

## Mapa del backend (`backend/app/`)

### Núcleo
| Archivo | Responsabilidad |
|---|---|
| `config.py` | Settings con prefijo `FINANZAS_` (BD, JWT, zona horaria, Telegram, SMTP) |
| `db.py` | Engine, `SessionLocal`, `get_db` |
| `models.py` | 25 tablas + enums |
| `schemas.py` | Pydantic (entradas/salidas) |
| `security.py` | Hash bcrypt + creación/validación de JWT |
| `deps.py` | `get_db`, `get_current_user` |
| `crud_utils.py` | `get_owned` (aislamiento por usuario) |
| `defaults.py` | Categorías y **etiquetas del diccionario** por defecto al registrarse (+ `sembrar_etiquetas_diccionario`) |
| `main.py` | App FastAPI + lifespan (arranca el scheduler) + registro de routers |

### Lógica de negocio
| Archivo | Responsabilidad |
|---|---|
| `recurrencia.py` | `hoy()` (zona horaria), `siguiente_pago()`, `factor_mensual()` y la generación de los cobros recurrentes: ingresos, suscripciones y **pólizas** |
| `alertas.py` | Pagos próximos: suscripciones, **primas y vencimiento de pólizas** y corte/pago de tarjetas |
| `reportes.py` | Agregación mensual y por categoría |
| `facturas.py` | Extracción de texto (pypdf + OCR tesseract con preprocesado) y heurísticas monto/fecha |
| `dinero.py` | **Parseo de dinero**: un solo parser para formato colombiano, US y mixto (signos, paréntesis, espacios internos, valores duplicados) y detección del formato del documento |
| `lineas.py` | Parser de recibos: parte un texto OCR en líneas de artículo (descripción, cantidad, valor) y detecta el tipo de documento |
| `clasificador.py` | Clasifica un artículo en cascada: historial (`reglas_ocr`) → diccionario → embeddings |
| `embeddings.py` | Embeddings **opcionales** (Ollama) para el tercer nivel del clasificador; sin `FINANZAS_OLLAMA_URL` no sale a la red |
| `presupuestos.py` | Límite mensual por categoría vs gasto real |
| `importacion.py` | Parser CSV flexible (delimitador, columnas, signos, formatos de monto; delega el dinero en `dinero.py`) |
| `mercado.py` | Comparativo de precios por tienda |
| `tasas.py` | Tasas de cambio: consulta, conversión y descarga desde internet |
| `intereses.py` | Simulador de pago de deuda y conversión **E.A. ↔ mensual** |
| `respaldo.py` | Exportar/restaurar todos los datos del usuario |
| `flujo.py` | Proyección de flujo de caja a N meses: ingresos recurrentes + cobros fijos (suscripciones y pólizas) + gasto variable, todo normalizado a COP |
| `metas.py` | Progreso de metas de ahorro y aporte sugerido |
| `tarjetas.py` | Deuda vigente de una tarjeta: último extracto (nivel) − pagos posteriores (flujo) |
| `saldos.py` | Saldo por cuenta y total, consolidado mensual y diagnóstico del sobregiro (las transferencias mueven dos cuentas y no cambian el total) |
| `polizas.py` | Costo de los seguros: prima normalizada a mes y a COP, resumen y desglose por tipo (lo comparten `/polizas` y `/reportes`) |
| `jerarquia.py` | Helpers del árbol `Categoría › Etiqueta › Subetiqueta` (rutas para mostrar) |
| `notificaciones.py` | Envío por Telegram / SMTP / WhatsApp + job diario con dedup |
| `scheduler.py` | Los 5 jobs: ingresos recurrentes, suscripciones vencidas, pólizas vencidas, TRM oficial y notificaciones |

### Routers (22)
`auth`, `categorias` (incluye `/arbol`), `cuentas`, `saldos`, `tarjetas`
(incluye simulador), `suscripciones`, `polizas` (incluye `/resumen` y
`/beneficiarios` y `/asegurados`), `transacciones`, `ingresos_recurrentes`,
`etiquetas` (incluye `/diccionario`), `alertas`, `reportes` (incluye `/seguros`), `facturas` (incluye el OCR por línea:
`/lineas`, `/lineas/{id}` y `/confirmar`), `presupuestos`, `importacion`,
`productos`, `lista_mercado`, `monedas` (monedas/tasas/convertir), `respaldo`,
`flujo`, `metas`, `notificaciones`.

---

## Modelo de datos

25 tablas de negocio (más `alembic_version`), creadas por 24 migraciones:

| Migración | Tablas |
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
| `0011_tasa_ea` | `tarjetas.tasa_interes_ea` |
| `0012_tarjeta_cuenta` | `tarjetas.cuenta_id` (débito → su cuenta) |
| `0013_etiquetas_en_categorias` | `etiquetas.categoria_id` + unicidad entre hermanos (índices funcionales) |
| `0014_arbol_unico` | migra subcategorías a etiquetas y **elimina `categorias.padre_id`** |
| `0015_suscripcion_etiqueta` | `suscripciones.etiqueta_id` |
| `0016_ocr_lineas` | `factura_lineas`, `reglas_ocr` (OCR por línea) |
| `0017_nombres_indices_orm` | renombra 22 índices al nombre que espera el ORM (`ix_tabla_columna`) |
| `0018_whatsapp` | `config_notificaciones.whatsapp_numero` (canal WhatsApp) |
| `0019_polizas` | `polizas`, `beneficiarios` + `transacciones.poliza_id` + `periodicidad.semestral` |
| `0020_poliza_asegurados` | `poliza_asegurados` (varias personas cubiertas por póliza) |
| `0021_uq_categorias_raiz` | recupera `uq_categorias_raiz` (sin el `WHERE` que la 0014 se llevó) y fusiona duplicados |
| `0022_transferencias` | tipo `transferencia` + `transacciones.cuenta_destino_id` |
| `0023_recurrentes_con_cuenta` | cuenta en las suscripciones y los ingresos recurrentes, y `transacciones.ingreso_recurrente_id` |
| `0024_pagos_tarjeta` | tabla `pagos_tarjeta`: el pago de la tarjeta como flujo (el extracto es el nivel) |

### Relaciones principales

```
usuarios ─┬─ cuentas ────────── transacciones   (saldo = inicial + ingresos − gastos)
          ├─ categorias ─┬───── presupuestos
          │              ├───── transacciones
          │              ├───── suscripciones
          │              ├───── ingresos_recurrentes
          │              └───── etiquetas       (el anidamiento vive AQUÍ:
          │                                      Categoría → Etiqueta → Subetiqueta;
          │                                      la categoría es siempre raíz)
          ├─ tarjetas ───┬───── transacciones
          │              ├───── suscripciones
          │              ├───── polizas        (el cargo de la prima)
          │              ├───── deudas_tarjeta  (deuda por moneda)
          │              └───── cuentas         (solo débito: instrumento de la cuenta)
          ├─ polizas ───┬────── beneficiarios  (nombre, parentesco, porcentaje)
          │              └────── poliza_asegurados (personas cubiertas; una es titular)
          ├─ transacciones ──┬─ etiquetas       (etiqueta_id, dentro del árbol)
          │                  ├─ polizas         (poliza_id: gasto generado por la prima)
          │                  └─ facturas ─── factura_lineas ─── reglas_ocr
          ├─ productos ──┬───── precios_mercado
          │              └───── lista_mercado
          ├─ metas_ahorro ───── aportes_meta
          └─ config_notificaciones
```

`etiquetas` es **autojerárquica dentro de una categoría** (`etiquetas.padre_id`): sin padre
es una etiqueta y con padre es una subetiqueta. Los nombres son únicos entre hermanos, sin
distinguir mayúsculas (índices `uq_etiquetas_raiz` / `uq_etiquetas_hija`).

`monedas` es referenciada por `cuentas`, `tarjetas`, `suscripciones`, `polizas`,
`transacciones`, `ingresos_recurrentes`, `presupuestos`, `precios_mercado`,
`metas_ahorro` y `tasas_cambio`.

Una **póliza** es un compromiso recurrente (prima + `proximo_pago`) con vigencia
(`fecha_inicio` / `fecha_fin`); cubre a una **persona** (`asegurado_nombre`, el principal) o a un **bien**
(los campos de vehículo), y el detalle de las personas cubiertas vive en
`poliza_asegurados` (una de ellas, como mucho, es la titular). Sus **beneficiarios** cuelgan
de ella y sus porcentajes no pueden sumar más de 100.

---

## Scheduler

Cinco jobs en `APScheduler` (en el proceso de la API):

| Job | Frecuencia | Qué hace |
|---|---|---|
| `ingresos-recurrentes` | cada 1 h | Genera la transacción de ingreso cuando `proxima_ejecucion <= hoy` y avanza la fecha (idempotente) |
| `suscripciones-vencidas` | cada 1 h | Genera el gasto de la suscripción al vencer y avanza un periodo (idempotente, tope de 24 periodos) |
| `polizas-vencidas` | cada 1 h | Genera el gasto de la **prima** al vencer y avanza `proximo_pago` (idempotente, tope de 24 periodos) |
| `trm-oficial` | cada 6 h | Trae la TRM oficial de la SFC (`datos.gov.co`) y la guarda como USD → COP |
| `notificaciones-pagos` | cada 1 h | Envía el resumen de pagos próximos; **máximo 1 al día** por usuario (dedup con `ultima_notificacion`) |

Se puede desactivar con `FINANZAS_SCHEDULER_ENABLED=false` (los tests lo hacen).

---

## Notificaciones

- **Config global del servidor**: `FINANZAS_TELEGRAM_BOT_TOKEN`, las `FINANZAS_SMTP_*`
  y `FINANZAS_WHATSAPP_TOKEN` / `FINANZAS_WHATSAPP_PHONE_ID`.
- **Config por usuario**: canal (`telegram` | `email` | `whatsapp` | `ambos` | `todos`),
  destino y días de anticipación.
- **Telegram**: `POST /notificaciones/telegram/detectar` lee `getUpdates` del bot para
  obtener el chat ID sin que el usuario lo busque a mano.
- **WhatsApp**: Cloud API de Meta. Fuera de la ventana de 24 h desde el último mensaje
  del usuario, Meta exige **plantilla aprobada** (*utility*); la app envía texto y
  propaga el error de Meta si falta.
- **Diseño extensible**: un canal nuevo es una función `enviar_*`, una entrada en
  `CANALES` y una opción en el selector; la lógica de alarmas y el scheduler no cambian.

---

## Frontend (`frontend/src/`)

- `api.ts` — `api()`, `apiUpload()`, `apiDownload()` (adjuntan el JWT).
- `auth.tsx` — contexto de sesión + guardas de ruta.
- `types.ts` — tipos compartidos.
- `components/Layout.tsx` — navegación.
- `pages/` — 21 pantallas (una por módulo): `Dashboard`, `Cuentas`, `Categorias`,
  `Transacciones`, `Tarjetas`, `Suscripciones`, `Polizas`, `IngresosRecurrentes`, `Etiquetas`,
  `Reportes`, `FlujoCaja`, `Presupuestos`, `Metas`, `Facturas`, `Importar`, `Mercado`,
  `Monedas`, `Respaldo`, `Notificaciones`, `Login`, `Register`.

---

## Convenciones

- **Dinero**: `NUMERIC(14,2)` → `Decimal` en Python; nunca `float` en cálculos.
- **Fechas**: `date` para días, `TIMESTAMP(timezone=True)` para auditoría.
- **Fechas "de hoy"**: siempre `recurrencia.hoy()`, que respeta
  `FINANZAS_TIMEZONE` (no `date.today()`).
- **Errores**: `HTTPException` con `detail` en español y códigos correctos
  (400 validación, 401 sin token, 404 no existe/no es tuyo, 502 fallo de un
  servicio externo).
- **Tests**: un test por módulo, contra PostgreSQL real, con truncado entre tests.
