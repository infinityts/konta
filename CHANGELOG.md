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

- **Costo anual de seguros dentro de *Reportes***: hoy el resumen vive en la página
  *Seguros* y las primas entran en el gasto fijo del dashboard, pero no aparecen en el
  desglose de reportes.
- **Varias personas cubiertas por póliza**: el modelo cubre el caso normal (un asegurado y
  sus beneficiarios). Una póliza familiar con varias personas aseguradas pediría una tabla
  `poliza_asegurados`.
- **Quitar un valor de un ENUM**: `periodicidad.semestral` se queda aunque se baje la
  migración `0019` (PostgreSQL no lo permite sin recrear el tipo).

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

## v1.4 — Editar tarjetas y validar la tasa

- **Se puede editar una tarjeta** (antes solo crear y borrar): botón *Editar* que rellena el
  formulario y guarda con `PATCH`. Era imposible corregir una tasa mal escrita sin borrar la tarjeta.
- **Validación de la tasa**: se rechaza con un mensaje claro si la tasa mensual supera el 20 %
  o la E.A. el 300 %. Esto atrapa el error típico de escribir `2.1593` (que es 215,93 %)
  creyendo que son 2,1593 %.
- **Mensaje del simulador más explícito**: ahora incluye la tasa mensual usada y avisa cuando es
  anormalmente alta.

## v1.5 — Editar movimientos y etiquetarlos

- **Se pueden editar los movimientos** (antes solo crear y borrar): botón *Editar* que abre el
  formulario con los datos actuales y guarda con `PATCH` — monto, fecha, descripción, categoría,
  subcategoría, cuenta, etiqueta.
- **Asignar etiquetas y subetiquetas** desde el propio movimiento, con la jerarquía indentada
  (`Hogar › Internet`), y **crear etiquetas en línea** sin salir del formulario
  (elige "es principal" o "subetiqueta de…").
- **Filtros**: por Gastos / Ingresos / Todos y búsqueda por descripción o categoría.
- El listado muestra la etiqueta con su ruta (`#Hogar › Internet`) y la cuenta.

## v1.6 — Tarjeta débito asociada a su cuenta

- **Concepto contable**: una **cuenta** es un activo (lo que tienes); una tarjeta **débito** es
  un **instrumento** de esa cuenta; una tarjeta **crédito** es un **pasivo** (lo que debes).
- Nuevo `tarjetas.cuenta_id`: las tarjetas de **débito** se asocian a su cuenta, para no contar
  el mismo dinero dos veces.
- En **Transacciones** ahora se elige la tarjeta: al elegir una de **débito**, la **cuenta se
  llena sola** con la de la tarjeta. Al elegir una de **crédito**, la cuenta se limpia y se
  avisa de que es un pasivo (su deuda se registra en Tarjetas).
- El formulario de tarjeta cambia según el tipo: **débito** pide la cuenta asociada; **crédito**
  pide corte, pago, cupo y tasa. Un crédito nunca queda asociado a una cuenta (el backend lo
  desasocia al cambiar de tipo).

## v1.7 — Etiquetas dentro de categorías (3 niveles) y sin duplicados

- **Nuevo modelo**: `Categoría → Etiqueta → Subetiqueta`. Las etiquetas ya no son una lista
  independiente: viven dentro de una categoría (`etiquetas.categoria_id`).
- **Nombres únicos entre hermanos**, sin distinguir mayúsculas ni minúsculas:
  - no dos **etiquetas** iguales dentro de la misma categoría
  - no dos **subetiquetas** iguales dentro de la misma etiqueta
  - no dos **categorías** iguales con el mismo padre
  - en categorías distintas el mismo nombre **sí** se permite
  - los mensajes de error explican cuál es el duplicado
- **Migración 0013**: agrega `categoria_id`, **limpia los duplicados existentes**
  (conserva uno y repunta movimientos, subetiquetas y demás referencias antes de borrar)
  y crea los índices únicos.
- **UI en cascada**: al registrar un movimiento se elige primero la categoría y el selector
  de etiquetas muestra solo las suyas; cambiar de categoría limpia la etiqueta.
- **Página Etiquetas** reorganizada por categoría, y aviso para las que quedaron sin categoría.

## v1.8 — Un solo árbol: Categoría → Etiqueta → Subetiqueta

- **Se elimina la redundancia**: antes había **dos jerarquías** en tablas distintas
  (`categorias.padre_id` para subcategorías y `etiquetas` para etiquetas/subetiquetas), y lo
  mismo se podía expresar de dos formas — causando duplicados como `Vivienda › Servicios`
  existiendo a la vez como subcategoría y como etiqueta.
- **Ahora hay un solo árbol**: las **categorías son siempre raíces** (Vivienda, Transporte,
  Casa 1…) y **todo el anidamiento vive en las etiquetas**.
- **Migración 0014**:
  - convierte cada subcategoría en una etiqueta de su categoría raíz (o la fusiona si ya existía),
    repuntando antes los movimientos (que pasan a la raíz + esa etiqueta), suscripciones,
    ingresos recurrentes, presupuestos y etiquetas;
  - borra las etiquetas huérfanas (sin categoría);
  - elimina `categorias.padre_id` y su índice.
- **Reportes y dashboard** ahora agrupan por `Categoría › Etiqueta › Subetiqueta`
  (el campo `subcategoria` del reporte pasa a llamarse `etiqueta`).
- **Editar** en **Etiquetas** (cambiar nombre, categoría o padre) y en **Categorías** (renombrar),
  sin tener que borrar y crear.

## v1.9 — Menú agrupado (barra superior) y loader

- **Navegación reagrupada**: las 18 opciones sueltas pasan a **`Resumen` + 5 grupos**
  (`Movimientos`, `Análisis`, `Organización`, `Herramientas`, `Configuración`),
  definidos en `src/nav.ts`. `Transacciones` sube al primer lugar de Movimientos.
- **Barra superior con desplegables** (`TopNav.tsx`): el submenú abre al **pasar el
  mouse** en escritorio (y con clic para teclado/táctil); cierra al navegar, al hacer
  clic fuera y con `Esc`; resalta el grupo y la opción activos según la ruta.
- **Móvil**: bajo 768 px aparece una **hamburguesa** con panel lateral y grupos en acordeón.
- **Contenido a ancho completo**: al quitar la barra lateral, las páginas ganan ~220 px.
- **Loader `AccordionLoader`**: nuevo alias `@` → `src`, componente
  `components/loading-ui/accordion-loader.tsx` (color por `currentColor`) y
  `AccordionLoaderColor` con los tres colores. Se usa como pantalla de carga.
- **Carga diferida (code splitting)**: cada página es un chunk aparte → el bundle inicial
  baja de **271 kB a 183 kB**, y el loader se muestra mientras baja cada página.

## v1.10 — Las suscripciones generan su gasto

Antes eran solo un recordatorio: **no aparecían** en el dashboard, presupuestos ni reportes.

- **`suscripciones.etiqueta_id`** (migración `0015`): cada suscripción lleva su etiqueta del
  árbol, así el cargo queda como `Suscripciones › Streaming › Netflix`.
- **`procesar_suscripciones()`**: al vencer, se crea la transacción de gasto heredando
  monto, moneda, categoría, etiqueta y tarjeta de la suscripción, y `proximo_pago` avanza
  un periodo. Es **idempotente** (una segunda pasada no duplica) y se pone al día con un
  tope de 24 periodos.
- **Job horario** en el scheduler (`suscripciones-vencidas`).
- `siguiente_pago()` respeta el fin de mes (31 ene → 28 feb) para semanal/mensual/trimestral/anual.
- **Validación de referencias**: categoría, tarjeta y etiqueta deben ser del usuario
  (antes un id ajeno daba error 500).
- **Frontend**: selector de etiqueta en cascada con la categoría, y la ruta (`Streaming › Netflix`)
  se muestra en el listado.

## v1.11 — Suscripciones editables y pausables

- **Editar** una suscripción (antes solo crear y borrar), con botón que rellena el formulario.
- **Pausar / activar**: una suscripción pausada o cancelada **no genera** su transacción
  (el job la ignora) y el listado muestra el estado.
- El listado muestra el **día de cobro mensual** («día 15 de cada mes») en lugar de la fecha
  completa, que confundía al leer un vencimiento puntual.

## v1.12 — OCR por línea (1/2: backend)

Primera mitad de la lectura de recibos **artículo por artículo** (la 2/2, que lo expone,
llega en la v1.17).

- **Migración `0016`**: tablas `factura_lineas` (un renglón detectado: descripción, cantidad,
  valor unitario, total, etiqueta, origen y confianza) y `reglas_ocr` (aprendizaje: «este
  artículo va siempre a esta etiqueta», único por `usuario_id` + `patron`).
- **OCR de fotos** (`facturas.py`): preprocesado antes de Tesseract (escala de grises,
  autocontraste, reescalado a ≥1000 px y binarizado) porque las fotos de recibos arrugados
  hacían fallar al OCR; soporte de JPG/PNG/WEBP además de PDF.
- **Parser de recibos colombianos** (`lineas.py`): separa descripción, cantidad y valor,
  entiende formatos de dos líneas y montos con separadores locales.
- **Clasificador** (`clasificador.py`) en cascada: **historial → diccionario → embeddings**,
  devolviendo el origen y la confianza de cada asignación.
- Los embeddings se calculan en Python (similitud coseno), **sin depender de pgvector**.

## v1.13 — TRM oficial y gasto fijo correcto

- **TRM oficial diaria** desde Datos Abiertos Colombia (`datos.gov.co`, Superintendencia
  Financiera) mediante el job `trm-oficial` cada 6 h, además del tipo de cambio de mercado
  (`open.er-api.com`) que ya existía.
- **Fix del «gasto fijo»**: sumaba las suscripciones en crudo, así que una suscripción
  **anual contaba como mensual** y una en **USD contaba como COP**. Ahora se normaliza la
  periodicidad a mensual y se convierte a COP con la tasa registrada.

## v1.14 — Dashboard con KPIs útiles

- **KPIs arriba**: ingresos del mes, gastos del mes y **gasto fijo** calculado por el backend
  (ya normalizado). Se elimina el KPI de suscripciones, que sumaba distinto que el resto.
- **Alertas en vez de prosa**: los avisos pasan a ser elementos accionables.
- **Un solo formato** de fecha (corto) en todo el dashboard.
- **Maquetas** de dashboard (accionable y analítico) en `frontend/public/dash-*.html` para
  revisar el diseño en la paleta real de la app.

## v1.15 — Categoría Telefonía por defecto

- Los usuarios nuevos reciben **11 categorías** por defecto: se añade **Telefonía** (gasto)
  al juego inicial.

## v1.16 — Correcciones tras la auditoría del sistema

- **Tests en verde**: los tests de categorías por defecto quedaron esperando 10 cuando se
  añadió Telefonía (11). Ahora leen **`N_DEFAULT = len(DEFAULT_CATEGORIAS)`** de
  `app/defaults.py`, así que añadir o quitar una categoría por defecto no vuelve a dejar la
  suite en rojo. Pasó de *2 failed, 30 passed* a **32 passed**.
- **Migración `0017` — nombres de índice alineados con el ORM**: las migraciones habían
  creado los índices con nombres cortos a mano (`ix_transacciones_usuario`) mientras
  SQLAlchemy espera `ix_transacciones_usuario_id`. `alembic check` reportaba ~40 operaciones
  falsas (borrar+crear el mismo índice), lo que hacía peligroso cualquier `--autogenerate`.
  Ahora se **renombran** los 22 índices (metadato, instantáneo) y queda creado el índice que
  faltaba de verdad: `metas_ahorro.usuario_id`.
- **Índices funcionales declarados en el ORM** (`__table_args__`): `uq_etiquetas_raiz`,
  `uq_etiquetas_hija` (unicidad entre hermanos, sin distinguir mayúsculas) y
  `uq_reglas_ocr_patron`. Estaban solo en SQL crudo, así que el autogenerate proponía
  borrarlos.
- **`factura_lineas.factura_id`** se declara `index=True` para que el modelo refleje su índice.
- **Downgrade arreglado**: la `0014` recreaba el FK de `categorias.padre_id` con otro nombre
  (`categorias_padre_id_fkey`) y el downgrade de la `0009` fallaba al borrar
  `fk_categorias_padre`. Ahora la `0014` conserva el nombre original, así que
  `alembic downgrade base` + `alembic upgrade head` corren completos.
- **Documentación al día**: este changelog (faltaban 9 commits), `docs/arquitectura.md`
  (21 tablas, 17 migraciones, 4 jobs del scheduler, `lineas.py` / `clasificador.py`, el árbol
  único) y el `README` (endpoints y estado). El `docker-compose.yml` usa `postgres:16`:
  pgvector no se usa (solo `pgcrypto`).

## v1.17 — OCR por línea (2/2): de código muerto a funcionalidad

La 1/2 dejó las tablas, el parser y el clasificador, pero **nada los usaba**: subías la
factura y su texto quedaba guardado sin partirlo. Ahora el flujo está cerrado.

- **Endpoints** (`/facturas`):
  - `POST /facturas/{id}/lineas` — parte el texto en artículos, los clasifica y los
    **persiste**. Es idempotente: al re-parsear descarta las líneas no confirmadas y
    conserva las que ya generaron transacción.
  - `PATCH /facturas/{id}/lineas/{linea_id}` — corrige descripción, valor o etiqueta.
    Al asignar etiqueta **aprende** la regla en `reglas_ocr`, así que la próxima factura
    la clasifica el nivel de historial.
  - `DELETE /facturas/{id}/lineas/{linea_id}` — descarta una línea.
  - `POST /facturas/{id}/confirmar` — crea **una transacción de gasto por línea**, con la
    categoría que sale de la etiqueta y la fecha de la factura (o la de hoy). Una línea ya
    confirmada no se puede editar ni borrar (409).
  - `GET /facturas/{id}` — factura con sus líneas y el **tipo de documento** detectado
    (mercado, gasolina, servicios, restaurante u otro).
- **Embeddings opcionales** (`app/embeddings.py`): tercer nivel del clasificador vía Ollama,
  con `FINANZAS_OLLAMA_URL` (vacío = desactivado, sin tocar la red). Los vectores se cachean
  por texto, así que el perfil de cada etiqueta se pide una vez y no una vez por línea. Si
  Ollama no responde, el nivel se salta: una factura **nunca** falla por el servicio de
  embeddings. Se usa `urllib` (biblioteca estándar), sin dependencias nuevas.
- **Frontend** (*Facturas*): botón **Leer líneas**, tabla editable con descripción,
  cantidad × valor unitario, valor total, **selector de etiqueta en cascada** por categoría
  (`Etiqueta › Subetiqueta`), badge del origen de la clasificación (historial / diccionario /
  embeddings / manual / sin clasificar), descartar línea, elegir cuenta y **Confirmar N
  líneas**. El input de subida acepta también **fotos** (JPG/PNG), no solo PDF.
- **Tests**: 35 en verde (antes 32). Cubren el parser (formatos de dos líneas, dinero
  colombiano, descarte de totales y medios de pago), el flujo completo
  parsear → clasificar → corregir → **re-clasificar por historial** → confirmar, el
  aislamiento entre usuarios y que una línea confirmada es inmutable.

## v1.18 — CI y backlog ordenado

- **CI en GitHub Actions** (`.github/workflows/ci.yml`): dos jobs en paralelo.
  *backend* levanta PostgreSQL 16 (la misma imagen oficial que `compose`, con `pgcrypto`),
  corre `alembic upgrade head`, **`alembic check`** —el paso que habría cazado la deriva de
  índices de la 0017— y `pytest`; *frontend* corre `pnpm install --frozen-lockfile` y
  `pnpm build` (que ya incluye `tsc --noEmit`). Badge en el README.
- El backlog vive en el Sistema de Contexto (RAG): se cerraron las 3 tareas demo que
  seguían como «pendientes» estando ya implementadas y se registraron las reales.

## v1.19 — WhatsApp como canal de notificaciones

Era el último canal pendiente. Se implementa con la **Cloud API oficial de Meta**, sin
gateways de terceros ni librerías no oficiales (que arriesgan el ban del número).

- **`config_notificaciones.whatsapp_numero`** (migración `0018`): el destino, en formato
  internacional sin `+` (ej. `573001234567`).
- **`enviar_whatsapp()`** (`notificaciones.py`): `POST` a
  `graph.facebook.com/<version>/<phone_id>/messages` con el token en la cabecera. Usa
  `urllib` de la biblioteca estándar: sin dependencias nuevas.
- **Config del servidor**: `FINANZAS_WHATSAPP_TOKEN`, `FINANZAS_WHATSAPP_PHONE_ID` y
  `FINANZAS_WHATSAPP_API_VERSION`. Sin token/phone_id el canal queda deshabilitado y el
  botón de prueba responde **502 con el mensaje de qué falta**, en vez de romper.
- **Canales**: se añade `whatsapp` y `todos` (los tres). `ambos` sigue significando
  *Telegram + correo*, así que las configuraciones existentes no cambian de significado.
- **Frontend**: opción WhatsApp en el selector de canal y campo del número destino.
- **Tests**: 36 en verde (antes 35). Cubren el mapeo de canales, que sin credenciales el
  canal avise en vez de reventar, el guardado del número por la API y el 502 del envío de
  prueba.
- **Aviso real de Meta**: fuera de la ventana de 24 h desde el último mensaje del usuario,
  la API exige una **plantilla aprobada** (*utility*); un texto libre se rechaza. Está
  documentado en el README y en `docs/despliegue.md`.

## v1.20 — Seguros y pólizas (personas y vehículos)

Una póliza es un compromiso recurrente **como una suscripción**, pero además tiene
vigencia y un bien o persona asegurada. Faltaba por completo.

- **Migración `0019`**: tablas `polizas` y `beneficiarios`, `transacciones.poliza_id`
  (trazabilidad del gasto) y el valor `semestral` en el tipo `periodicidad`.
  *Nota*: PostgreSQL no permite quitar un valor de un ENUM, así que `semestral` se queda
  aunque se baje la migración (inofensivo).
- **`polizas`**: tipo (`vida`, `salud`, `vehiculo`, `hogar`, `otro`), aseguradora y número
  de póliza; **asegurado** persona (`asegurado_nombre`) **o bien** (vehículo con `placa`,
  `marca`, `modelo`, `anio` y `valor_asegurado`); prima, moneda y periodicidad; vigencia
  (`fecha_inicio` / `fecha_fin`), `renovacion_automatica` y `proximo_pago`; categoría,
  etiqueta, tarjeta y cuenta del cargo; estado (activa/pausada/cancelada).
- **`beneficiarios`**: nombre, parentesco y porcentaje. La API **rechaza** que los
  porcentajes de una póliza sumen más de 100, diciendo cuánto suman.
- **El gasto se genera solo**: nuevo job `polizas-vencidas` (cada hora) con
  `procesar_polizas()`, idempotente y con puesta al día (tope de 24 periodos). La
  transacción hereda categoría, etiqueta, tarjeta y cuenta, y queda enlazada a la póliza.
  Una póliza pausada o cancelada no genera nada.
- **Alertas**: `poliza_pago` para la prima próxima y `poliza_vencimiento` para el fin de
  vigencia (no avisa si la póliza renueva automáticamente).
- **Costo de los seguros**: `GET /polizas/resumen` devuelve prima **mensual** y **anual**
  normalizadas a COP (semestral pesa 1/6, anual 1/12) e informa de las monedas sin tasa
  de cambio, en vez de sumarlas mal.
- **`periodicidad` gana `semestral`** y el factor de normalización se centraliza en
  `recurrencia.factor_mensual()` (antes duplicado y sin semestral en `saldos.py`).
- **El gasto fijo del diagnóstico** ahora suma suscripciones **y pólizas**, normalizadas.
- **Frontend**: página *Seguros* (grupo Movimientos) con resumen de primas, formulario que
  cambia según el tipo (los campos del vehículo solo aparecen en vehículo), edición,
  pausar/activar y gestión de beneficiarios con el porcentaje repartido.
- **Tests**: 41 en verde (antes 36).

### Y un agujero que apareció al hacerlo

El **respaldo** solo exportaba 11 de los 21 modelos: al restaurar se perdían **cuentas,
metas de ahorro y sus aportes, deudas de tarjeta, líneas de factura, reglas de OCR y la
configuración de notificaciones** (y las pólizas nuevas). Ahora exporta y restaura todo,
en orden de dependencias y con `flush` por modelo — sin `relationship()` declaradas, el
orden de INSERT no se deduce solo (fue justo el fallo que apareció en el test: los
aportes se insertaban antes que su meta).

## v1.21 — Flujo de caja: monedas, pólizas y doble conteo

Tres fallos en la proyección, uno de ellos metido por la v1.20.

- **Monedas mezcladas**: `fijos_por_mes[clave] += sub.monto` sumaba los importes en crudo,
  así que una suscripción de **USD 10** contaba como **$10** y el balance mezclaba monedas.
  Ahora cada importe se convierte a COP con la tasa registrada (igual que el gasto fijo del
  dashboard desde la v1.13) y, si falta la tasa, ese cobro **no se suma** y la moneda sale
  en el nuevo campo `sin_tasa` — la UI lo avisa y dice dónde registrarla. El endpoint
  declara `moneda: "COP"`. Lo mismo para los **ingresos** recurrentes, que tenían el
  problema idéntico.
- **Las pólizas no aparecían**: el flujo solo miraba las suscripciones, así que la prima de
  un seguro no salía en la proyección. Ahora entran como cobro fijo, en los meses en que
  toca pagarlas.
- **Periodicidad semestral**: `_ocurrencias_suscripcion` no tenía `SEMESTRAL` en su mapa de
  pasos, así que caía al valor por defecto (1 mes) y **una prima semestral se proyectaba
  como si se pagara todos los meses**. El mapa ya lo incluye (y la función, ahora
  `_ocurrencias_cobro`, sirve para suscripciones y pólizas).
- **Doble conteo (regresión de la v1.20)**: el gasto variable solo excluía las
  transacciones con `suscripcion_id`, así que las que genera una **póliza** entraban al
  promedio variable *además* de contar como gasto fijo. Ahora se excluyen también por
  `poliza_id`.

Tests: 44 en verde (antes 41). Los tres fallos se reprodujeron primero con tests que
fallaban, y cubren la conversión, el reparto de la prima semestral, el aviso de moneda sin
tasa y que una prima no se cuente dos veces.
