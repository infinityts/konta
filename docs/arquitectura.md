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
| `models.py` | 18 tablas + enums |
| `schemas.py` | Pydantic (entradas/salidas) |
| `security.py` | Hash bcrypt + creación/validación de JWT |
| `deps.py` | `get_db`, `get_current_user` |
| `crud_utils.py` | `get_owned` (aislamiento por usuario) |
| `defaults.py` | Categorías por defecto al registrarse |
| `main.py` | App FastAPI + lifespan (arranca el scheduler) + registro de routers |

### Lógica de negocio
| Archivo | Responsabilidad |
|---|---|
| `recurrencia.py` | Ocurrencias de ingresos recurrentes + `hoy()` (zona horaria) |
| `alertas.py` | Pagos próximos (suscripciones + corte/pago de tarjetas) |
| `reportes.py` | Agregación mensual y por categoría |
| `facturas.py` | Extracción de texto (pypdf + OCR tesseract) y heurísticas monto/fecha |
| `presupuestos.py` | Límite mensual por categoría vs gasto real |
| `importacion.py` | Parser CSV flexible (delimitador, columnas, signos, formatos de monto) |
| `mercado.py` | Comparativo de precios por tienda |
| `tasas.py` | Tasas de cambio: consulta, conversión y descarga desde internet |
| `intereses.py` | Simulador de pago de deuda (interés compuesto mensual) |
| `respaldo.py` | Exportar/restaurar todos los datos del usuario |
| `flujo.py` | Proyección de flujo de caja a N meses |
| `metas.py` | Progreso de metas de ahorro y aporte sugerido |
| `saldos.py` | Saldo por cuenta y total, consolidado mensual y diagnóstico del sobregiro |
| `jerarquia.py` | Helpers de categoría → subcategoría |
| `notificaciones.py` | Envío por Telegram/SMTP + job diario con dedup |
| `scheduler.py` | Jobs: ingresos recurrentes y notificaciones (cada hora) |

### Routers (21)
`auth`, `categorias` (incluye `/arbol`), `cuentas`, `saldos`, `tarjetas`
(incluye simulador), `suscripciones`, `transacciones`, `ingresos_recurrentes`,
`etiquetas`, `alertas`, `reportes`, `facturas`, `presupuestos`, `importacion`,
`productos`, `lista_mercado`, `monedas` (monedas/tasas/convertir), `respaldo`,
`flujo`, `metas`, `notificaciones`.

---

## Modelo de datos

19 tablas de negocio (más `alembic_version`), creadas por 11 migraciones:

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

### Relaciones principales

```
usuarios ─┬─ cuentas ────────── transacciones   (saldo = inicial + ingresos − gastos)
          ├─ categorias ─┬───── presupuestos
          │              ├───── transacciones
          │              ├───── suscripciones
          │              ├───── ingresos_recurrentes
          │              └───── categorias     (autojerárquica: categoría → subcategoría)
          ├─ tarjetas ───┬───── transacciones
          │              ├───── suscripciones
          │              └───── deudas_tarjeta  (deuda por moneda)
          ├─ transacciones ──┬─ etiquetas       (autojerárquica)
          │                  └─ facturas
          ├─ productos ──┬───── precios_mercado
          │              └───── lista_mercado
          ├─ metas_ahorro ───── aportes_meta
          └─ config_notificaciones
```

`monedas` es referenciada por `cuentas`, `tarjetas`, `suscripciones`,
`transacciones`, `ingresos_recurrentes`, `presupuestos`, `precios_mercado`,
`metas_ahorro` y `tasas_cambio`.

---

## Scheduler

Dos jobs en `APScheduler` (en el proceso de la API):

| Job | Frecuencia | Qué hace |
|---|---|---|
| `ingresos-recurrentes` | cada 1 h | Genera la transacción de ingreso cuando `proxima_ejecucion <= hoy` y avanza la fecha (idempotente) |
| `notificaciones-pagos` | cada 1 h | Envía el resumen de pagos próximos; **máximo 1 al día** por usuario (dedup con `ultima_notificacion`) |

Se puede desactivar con `FINANZAS_SCHEDULER_ENABLED=false` (los tests lo hacen).

---

## Notificaciones

- **Config global del servidor**: `FINANZAS_TELEGRAM_BOT_TOKEN` y las `FINANZAS_SMTP_*`.
- **Config por usuario**: canal (`telegram` | `email` | `ambos`), destino y días de anticipación.
- **Telegram**: `POST /notificaciones/telegram/detectar` lee `getUpdates` del bot para
  obtener el chat ID sin que el usuario lo busque a mano.
- **Diseño extensible**: agregar WhatsApp sería un canal más en
  `notificaciones.py` + una opción en el selector; la lógica de alarmas y el
  scheduler no cambian.

---

## Frontend (`frontend/src/`)

- `api.ts` — `api()`, `apiUpload()`, `apiDownload()` (adjuntan el JWT).
- `auth.tsx` — contexto de sesión + guardas de ruta.
- `types.ts` — tipos compartidos.
- `components/Layout.tsx` — navegación.
- `pages/` — 18 pantallas (una por módulo).

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
