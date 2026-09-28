# Changelog

Historial de Konta, en orden cronológico. Cada entrada corresponde a un commit en
`main`.

## v1.0 — Backlog completo

### Núcleo
- **Backend inicial** (`4a08447`): FastAPI + SQLAlchemy + Alembic + PostgreSQL,
  auth multi-usuario (JWT + bcrypt), CRUD de categorías, tarjetas, suscripciones
  y transacciones, y categorías por defecto al registrarse.
- **Frontend inicial** (`df70eff`): React + Vite + TypeScript + Tailwind, login,
  registro, dashboard y CORS + `/auth/me` en el backend.
- **Pantallas CRUD** (`16f7fa6`): tarjetas, suscripciones y transacciones.
- **Docker** (`93e2a2a`): Dockerfiles del backend y del frontend + nginx con proxy
  `/api` + `docker-compose.yml`.
- **Conciliación ingresos vs gastos** (`8aa314b`): balance del mes y filtro de
  categorías por tipo.

### Organización y alertas
- **Ingresos recurrentes** (`5701148`): periodicidad diaria, semanal y mensual, con
  generación automática por scheduler (y *catch-up*).
- **Dashboard: top categorías** (`277c22e`): desglose de gastos del mes con barras.
- **Etiquetas y subetiquetas** (`ca522e4`): jerárquicas, asociables a transacciones.
- **Alarmas de pagos** (`7f087be`): próximos vencimientos de suscripciones y de
  tarjetas (pago y corte).

### Análisis
- **Reportes** (`ac3a749`): evolución mensual (ingresos vs gastos) y desglose por
  categoría, con página propia.
- **Presupuestos por categoría** (`404212f`): límite mensual, gasto real, % consumido
  y aviso de exceso.
- **Proyección de flujo de caja** (`1aae317`): a 3/6/12 meses combinando ingresos
  recurrentes, suscripciones y gasto variable promedio.

### Documentos y datos
- **OCR de facturas PDF** (`d1a442d`): subida, extracción de texto (pypdf + tesseract)
  y detección heurística de monto y fecha; asociación a transacciones.
- **Importar estado de cuenta (CSV)** (`6f6f183`): parser flexible con
  previsualización y confirmación.
- **Exportar y respaldar** (`13a2d31`): respaldo completo en JSON, transacciones en
  CSV y restauración desde el respaldo.
- **Documentación** (`14fd527`, `973c018`): README completo + guía de despliegue.

### Mercado y dinero
- **Mercado** (`b10f102`): lista de compras con total estimado y comparativo de
  precios por tienda (detecta la más barata).
- **Multi-moneda** (`11f4703`): catálogo de monedas, tasas manuales o descargadas
  desde internet (open.er-api.com) y conversor.
- **Simulador de intereses de tarjeta** (`cef08e1`): meses para pagar, total de
  intereses y aviso si el pago no cubre el interés.

### Ahorro y avisos
- **Metas de ahorro** (`c98abbd`): objetivo, aportes, progreso y aporte mensual
  sugerido según la fecha límite.
- **Notificaciones** (`61a9b4a`): resumen diario de pagos por **Telegram** y/o
  **correo**, con días de anticipación configurables, dedup diario, envío de prueba
  y detección automática del chat ID.

## v1.1 — Estado de cuenta real

- **Cuentas con saldo inicial**: cada cuenta (efectivo, banco, ahorros)
  tiene su saldo inicial y cada transacción puede asignarse a una cuenta. El saldo
  actual es `saldo inicial + ingresos − gastos`, por cuenta y total.
- **Consolidado mes a mes** con saldo inicial, ingresos, gastos, balance y **saldo
  final corrido**.
- **Subcategorías**: las categorías ahora son jerárquicas (categoría → subcategoría);
  el dashboard y los reportes agrupan por ambas.
- **Diagnóstico del saldo**: si estás **sobregirado**, el dashboard explica **por qué**
  (categorías que más pesan, gastos fijos, comparación con el mes anterior e ingresos).
- **Páginas nuevas**: *Cuentas* (con el consolidado) y *Categorías* (jerarquía).

---

## Pendiente / ideas

- **WhatsApp** como canal de notificaciones. Opciones evaluadas:
  - **Cloud API oficial de Meta**: sin mensualidad, ~US$0.0008 (≈ COP 3) por mensaje
    *utility* en Colombia. Requiere cuenta Meta Business, número dedicado, plantilla
    aprobada y método de pago.
  - **Gateway de terceros** (CallMeBot) o librerías no oficiales (Baileys): gratis,
    pero con **riesgo de ban** del número por violar los términos de WhatsApp.
- Edición (PATCH) en la UI para tarjetas, suscripciones y transacciones.
- Página de administración de categorías.

## v1.1.1 — Correcciones tras validar con datos reales

- **Diagnóstico del saldo sin cuentas**: si no hay cuentas configuradas, el dashboard
  ahora lo dice explícitamente («el saldo que ves es solo el flujo, no tu dinero») con
  un botón directo para crear la cuenta con el saldo inicial. El rótulo cambia a
  *Flujo acumulado (sin saldo inicial)* para no llamar «saldo» a lo que no lo es.
- **Próximo ingreso recurrente** visible en el dashboard (nombre, monto y fecha) para
  que no sorprenda que un salario del día 30 aún no esté sumado.
- **Preselección de cuenta** al registrar una transacción (si solo hay una) y aviso
  cuando se guarda sin cuenta.
- **`POST /cuentas/{id}/adoptar-movimientos`**: asigna en bloque todos los movimientos
  que quedaron sin cuenta, para poner al día un saldo ya existente.

## v1.2 — Deuda de tarjeta

- **Deuda por moneda**: una tarjeta puede deber en varias monedas a la vez (el caso real
  del extracto AMEX: `COP 8.912.816` + `USD 700`). Se registra con fecha y notas.
- **Total en COP**: si hay tasa de cambio registrada (p. ej. la TRM), el listado muestra
  la deuda total convertida; si falta, avisa cuál tasa registrar.
- **Simulador conectado**: si no indicas saldo, el simulador usa la **deuda registrada**
  de la tarjeta en vez de volver a escribirla.
- Nuevos endpoints `GET/POST /tarjetas/{id}/deudas` y `DELETE /tarjetas/{id}/deudas/{deuda_id}`.

## v1.3 — Tasa del extracto (E.A. → mensual)

- Las tarjetas colombianas publican la tasa **efectiva anual (E.A.)**, pero la app pedía la
  mensual en decimal: confuso y fácil de escribir mal.
- Ahora el formulario acepta **E.A. (%)** o **mensual (%)** y convierte solo con la fórmula
  correcta `(1+EA)^(1/12)−1` — **no** dividiendo entre 12 (25,93 % E.A. = 1,94 %/mes, no 2,16 %).
- Se guardan ambas (`tasa_interes_ea` y `tasa_interes`) y el listado muestra las dos.
- El simulador sigue usando la mensual ya convertida.
