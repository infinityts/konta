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

Los criterios de aceptación de lo que sigue viven en el backlog del Sistema de Contexto
(RAG); aquí queda el **porqué** de cada decisión, para que no se pierda.

- **Dos huecos de UI** (el backend ya lo permite): **borrar un aporte** a una meta —hoy un
  monto mal tecleado obliga a borrar la meta entera— y **editar o borrar un producto** del
  mercado.

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

## v1.22 — Costo de los seguros en Reportes

Era el pendiente que quedó de la v1.20: el resumen de seguros vivía solo en su página.

- **`GET /reportes/seguros`**: prima mensual y anual de las pólizas activas, con
  **desglose por tipo** (vida, vehículo…) ordenado por costo, y las monedas sin tasa.
- **La página *Reportes*** gana el bloque *Costo de los seguros* con los totales y la tabla
  por tipo. Aparece solo si hay pólizas activas, y avisa si falta una tasa de cambio.
- **`app/polizas.py`**: la lógica de seguros sale del router a su propio módulo, porque
  ahora la usan dos sitios (`/polizas/resumen` y `/reportes/seguros`) — mismo patrón que
  `app/reportes.py` con su router. Un solo sitio donde se calcula la prima mensual en COP.
- Tests: 45 en verde (antes 44). El nuevo comprueba la normalización (anual y semestral al
  mes), el desglose por tipo, que una póliza pausada no cuenta, que una moneda sin tasa no
  se suma pero se informa, el aislamiento entre usuarios y que los dos endpoints coinciden.

## v1.23 — Varias personas aseguradas por póliza

El modelo cubría un asegurado más beneficiarios, que es el caso de un seguro individual.
Una **póliza familiar** cubre a varias personas, y no había dónde ponerlas.

- **Migración `0020`**: tabla `poliza_asegurados` (nombre, parentesco, fecha de nacimiento,
  `es_titular`), con `ON DELETE CASCADE` desde la póliza.
- **Endpoints**: `POST /polizas/{id}/asegurados`, `PATCH|DELETE /polizas/asegurados/{id}`.
  La póliza devuelve sus asegurados junto a los beneficiarios.
- **Un solo titular**: al marcar otro, el anterior deja de serlo (el servidor lo desmarca,
  no se confía a que el cliente lo haga).
- **Validación**: la fecha de nacimiento no puede estar en el futuro (422).
- `polizas.asegurado_nombre` **se conserva**: sigue siendo la persona asegurada principal (o
  el tomador, en vehículo) y es lo que usa el título de la póliza.
- **Frontend**: el panel de la póliza pasa a *Personas cubiertas* y muestra las dos listas
  (asegurados y beneficiarios), con alta, baja y «Hacer titular».
- **Respaldo**: `poliza_asegurados` entra en la exportación y la restauración (si no, se
  habrían perdido al restaurar, como pasó con las otras tablas en la v1.20).
- Tests: 46 en verde (antes 45). El nuevo cubre el alta de varias personas, que el titular
  es único, la fecha futura, el aislamiento entre usuarios y el borrado en cascada.

## v1.24 — Test de migraciones con datos (y el bug que destapó)

Todas las pruebas de migraciones migraban una base **vacía**: eso no prueba nada de las
migraciones que **mueven datos**, que son las que pueden romper un despliegue real. Faltaba
justo lo que llevo dos rondas diciendo que era el riesgo no cubierto.

- **`tests/test_migraciones.py`**: crea su propia base y reproduce el despliegue por
  versiones con filas dentro — datos de la `0012` (categorías con hijos, etiquetas sueltas,
  duplicados), la `0013` fusionando duplicados y repuntando movimientos, el paso en que el
  usuario re-categoriza sus etiquetas con la app de la v1.7, y la `0014` convirtiendo
  subcategorías en etiquetas. Comprueba que **no se pierde ninguna transacción**, que la
  subcategoría queda como etiqueta dentro de su categoría, que las referencias
  (transacciones, presupuestos, suscripciones, ingresos recurrentes) se repuntan, que el
  movimiento sin clasificar no se toca y que la base termina en `head` con las tablas nuevas.

### El bug que apareció

Con filas dentro, el test falló al comprobar la unicidad de categorías:

- La `0013` creó `uq_categorias_raiz` como índice **parcial** (`... WHERE padre_id IS NULL`).
- La `0014` eliminó `categorias.padre_id` y **PostgreSQL se llevó el índice por delante**,
  porque su cláusula `WHERE` usaba esa columna. La `0014` solo se acordó de borrar
  `uq_categorias_hija`.
- Desde entonces las **categorías no tenían ninguna garantía de unicidad en la base**: solo
  la comprobaba el código de la API. Un script, un `INSERT` a mano o una carrera entre dos
  peticiones podían dejar dos «Vivienda» sin que nada lo impidiera.

**Migración `0021`**: fusiona los duplicados que se hayan podido crear en ese hueco
(conserva el id menor y repunta transacciones, suscripciones, ingresos recurrentes,
presupuestos, etiquetas y **pólizas**) y crea el índice único
`uq_categorias_raiz (usuario_id, lower(nombre))` — ya sin `WHERE`, porque ahora toda
categoría es raíz. El índice se declara también en `Categoria.__table_args__` para que
`alembic check` siga limpio.

Dos tests: el del despliegue completo y uno específico que parte de una base **con
duplicados ya creados** para comprobar que la `0021` los fusiona en vez de fallar al
desplegar (que era el riesgo real de "crear el índice a secas").

Tests: 48 en verde (antes 46).

### Aviso de despliegue

Del test sale un aviso que no estaba escrito en ninguna parte: **una etiqueta que llegue a la
`0014` sin `categoria_id` se borra** (es el comportamiento que documenta el v1.8, pero no su
implicación operativa). Solo afecta a quien actualice desde la v1.7 o anterior: hay que
re-categorizar las etiquetas entre la `0013` y la `0014`. Queda anotado en
`docs/despliegue.md`.

## v1.25 — El OCR, usable de fábrica (y con la tarjeta)

Al probarlo con un usuario nuevo aparecieron dos huecos que hacían la función poco práctica:
**no clasificaba nada** y **no preguntaba de dónde salía el dinero**.

### Clasificaba, pero no para un usuario nuevo

El diccionario empareja contra **nombres de etiquetas**, y un usuario nuevo recibía las 11
categorías y **cero etiquetas**: una tira de D1 de 6 artículos salía entera «sin
clasificar». Había que crear a mano las etiquetas con los nombres exactos que espera el
diccionario, y nada te decía cuáles eran.

- **`ETIQUETAS_DICCIONARIO`** (`defaults.py`): al registrarse se crean las etiquetas que el
  diccionario reconoce, en su categoría natural — *Mercado* (Carnes, Frutas y verduras,
  Lácteos y huevos, Despensa, Aseo del hogar, Cuidado personal), *Transporte* (Gasolina) y
  *Otros gastos* (Ropa, Calzado, Tecnología).
- **`POST /etiquetas/diccionario`**: crea las que falten para quien ya tenía cuenta, sin
  tocar nada más (idempotente, y se salta las categorías que el usuario haya renombrado o
  borrado). En *Facturas* aparece un botón cuando hay líneas sin clasificar, y vuelve a
  clasificar solo.
- **Un test guarda la coherencia**: si alguien añade una etiqueta a `ETIQUETAS_DICCIONARIO`
  que el diccionario no conoce (o al revés), el test falla. Se siembra para nada y nadie se
  enteraría.

### El diccionario tampoco sabía de ropa

Una compra de jeans, camisetas y zapatillas salía entera «sin clasificar», y al confirmar
las transacciones quedaban **sin categoría** — o sea, invisibles para los reportes por
categoría y para los presupuestos. Se añaden tres grupos al diccionario: **Ropa**, **Calzado**
y **Tecnología**, sembrados en *Otros gastos* (no hay categoría propia para ellos).

### No preguntaba la tarjeta

`POST /facturas/{id}/confirmar` solo aceptaba `cuenta_id`, así que el gasto del OCR quedaba
**sin tarjeta**: no cuadraba con el extracto. Ahora acepta también `tarjeta_id` y `fecha`:

- Si la tarjeta es de **débito**, la transacción **hereda su cuenta** (una tarjeta de débito
  es un instrumento de esa cuenta, no un saldo aparte).
- Si es de **crédito**, el gasto no toca la cuenta (es un pasivo) y la UI lo avisa.
- La **fecha** permite registrar la compra en su día real cuando el recibo no la trae
  legible; si no se indica, se usa la detectada o la de hoy.
- En *Facturas* el panel de líneas gana selector de tarjeta, selector de cuenta y fecha, con
  la misma regla que *Transacciones* (el débito llena la cuenta, el crédito la limpia).

Tests: 52 en verde (antes 48). Los nuevos cubren la clasificación automática de una tira de
mercado y de una compra de ropa, la tarjeta (crédito y débito con herencia de cuenta), la
fecha, el sembrado idempotente de las etiquetas, el aislamiento entre usuarios al usar una
tarjeta ajena y la coherencia entre el diccionario y las etiquetas por defecto.

## v1.26 — Clasificar una tira larga de golpe

Con 30 líneas, corregir una por una no es viable, y una compra que el diccionario no conoce
generaba gastos **sin categoría** (invisibles para reportes y presupuestos).

- **`PATCH /facturas/{id}/lineas`** (en bloque): asigna una etiqueta a **muchas líneas de una
  vez**. Por defecto solo toca las que están **sin clasificar** —lo que el diccionario acertó
  no se pisa— y con `solo_sin_clasificar: false` se puede sobrescribir todo, o quitar la
  etiqueta (`etiqueta_id: null`). **Cada asignación se aprende** en `reglas_ocr`, así que la
  próxima compra de lo mismo ya sale clasificada.
- **Categoría de respaldo al confirmar**: `POST /facturas/{id}/confirmar` acepta
  `etiqueta_id` o `categoria_id` para las líneas que sigan sin clasificar. Si se indica la
  etiqueta, su categoría manda; si solo la categoría, el gasto cae ahí. Se acabó el gasto
  huérfano de categoría.
- **Frontend**: en *Facturas*, bloque *«Asignar a las N sin clasificar»* (categoría → etiqueta
  en cascada + **Aplicar**, con el aviso de que se aprende) y, al confirmar, un selector de
  **categoría de respaldo** con la explicación de por qué conviene elegirla.
- Tests: 54 en verde (antes 52). Cubren el filtrado (solo las sin clasificar), el aprendizaje
  tras la asignación en bloque, la sobrescritura explícita, el borrado de etiquetas, el aviso
  cuando el filtro no encaja con nada, la categoría de respaldo y el aislamiento entre
  usuarios.

## v1.27 — Transferencias entre cuentas

Era el hueco más grande: `TipoTransaccion` solo tenía `ingreso` y `gasto`, así que mover dinero
de ahorros a la cuenta del día a día obligaba a registrar **un gasto y un ingreso del mismo
monto**. Los saldos quedaban bien, pero los **reportes y el flujo de caja se contaminaban** con
un gasto y un ingreso que nunca existieron.

- **Migración `0022`**: valor `transferencia` en el ENUM `tipo_transaccion` y columna
  `transacciones.cuenta_destino_id` (la cuenta que recibe; el origen va en `cuenta_id`).
- **Una transferencia no es gasto ni ingreso**, y con el tipo nuevo queda **fuera por
  construcción** de todo lo que ya filtraba por tipo: reportes, presupuestos, alertas, flujo de
  caja y el gasto variable. Lo que **sí** hubo que tocar es el cálculo de saldos, que tenía dos
  trampas:
  - `_neto()` metía en el `else` cualquier tipo que no fuera `ingreso`, así que una
    transferencia **restaba como un gasto**. Ahora la salta.
  - `saldo_cuentas`/`saldo_de_cuenta` agregaban solo por `cuenta_id`, así que la transferencia
    **no movía ninguna cuenta**. Ahora se agregan las dos direcciones (sale de `cuenta_id`,
    entra en `cuenta_destino_id`) y el consolidado la ignora porque mover dinero entre tus
    cuentas **no cambia el total**.
- **Reglas en un solo sitio** (`routers/transacciones.py`): la transferencia exige origen y
  destino distintos, ambos del usuario y en la **misma moneda**, y **prohíbe** categoría,
  etiqueta, tarjeta y suscripción (no es un consumo que se clasifique). Al **editar** se valida
  el estado *resultante*, no solo lo que llega: convertir un gasto en transferencia obliga a
  quitarle la categoría y darle destino.
- **UI**: opción *Transferencia entre cuentas* en el formulario, con «Desde» y «Hacia» en lugar
  de categoría/tarjeta; en el listado se lee `🔄 Ahorros → Diario` sin signo ni color de gasto, y
  hay filtro propio. En **Cuentas** se ven los movimientos por transferencia de cada cuenta para
  que el saldo no parezca inventado.
- Nota: entre monedas distintas la transferencia se **rechaza** con un mensaje claro — eso
  necesita su propia tasa y un segundo importe (`monto_destino`), que es otra tarea.
- Tests: 56 en verde (antes 54). Cubren que el saldo se mueva en las dos cuentas y **no** en los
  reportes, el flujo ni el diagnóstico; y las validaciones (sin destino, mismo origen y destino,
  con categoría, entre monedas, con cuentas ajenas y la conversión de un gasto en transferencia).

### Lo que queda de la tarjeta

El **pago de la tarjeta** se separa a su propia tarea, porque no es solo una transferencia: la
deuda se guarda como snapshots («lo que dice el extracto», un *nivel*) y sumarle pagos como
filas negativas se rompe en cuanto registres el extracto siguiente. El `CHANGELOG` deja las
tres opciones de modelo sobre la mesa.

## v1.28 — «Casa 2» nace con las etiquetas de «Casa 1»

Crear una segunda vivienda (o un segundo coche, o cualquier cosa que se repita) obligaba a
volver a teclear el mismo árbol de etiquetas: *Servicios › Internet, Agua*, *Aseo › Señora*,
*Arriendo*… Y como el diccionario del OCR empareja contra **nombres de etiquetas**, teclear
una variante («Internet» contra «Internet Casa 2») rompía de paso la clasificación automática.

- **`POST /categorias/{id}/copiar-etiquetas`** con `{origen_id}`: trae el árbol de otra
  categoría —etiquetas **y subetiquetas**, conservando el anidamiento— dentro de esta.
  - **No duplica**: lo que ya exista se informa en `omitidas`. Y si una raíz ya está pero le
    faltan hijas, **se añaden** (copiar *Servicios › Internet, Agua* sobre una categoría que
    ya tiene *Servicios* añade las dos hijas, no una segunda *Servicios*).
  - **Idempotente**: repetirlo no añade nada.
  - **`previsualizar: true` devuelve el plan sin guardar nada** (hace `rollback`), que es lo
    que permite enseñar «se crearán 6 etiquetas: Servicios › Internet, …» antes de tocar nada.
  - Rechaza copiar sobre la **misma** categoría y entre categorías de **distinto tipo**
    (una etiqueta de ingresos dentro de una de gastos rompería los reportes por tipo y los
    presupuestos, que dan por hecho esa coherencia).
- **Se copia, no se comparte** — y es una decisión, no una limitación: aquí una etiqueta vive
  dentro de una categoría (`etiquetas.categoria_id`) y los reportes agrupan por
  `Categoría › Etiqueta › Subetiqueta`. Compartir la misma etiqueta entre dos categorías
  exigiría una relación N:M y decidir **qué categoría aparece en el reporte** cuando un gasto
  usa una etiqueta que pertenece a dos; además rompería la unicidad «entre hermanos dentro de
  una categoría». Copiando, cada casa es independiente: renombrar «Internet» en Casa 1 no
  cambia Casa 2.
- **UI**: en *Categorías*, cada una tiene **«Copiar etiquetas de…»**; al elegir el origen se
  ve el plan (lo que se crea y lo que ya existía) y solo entonces se confirma.
- La lógica del árbol vive en `jerarquia.py` (`copiar_etiquetas`), junto a los demás helpers
  de `Categoría › Etiqueta › Subetiqueta`, y es recursiva por si algún día hay más de tres
  niveles.
- Tests: 58 en verde (antes 56). Cubren la previsualización (que **no** crea nada), el
  anidamiento copiado, la idempotencia, las hijas que se añaden bajo una raíz existente, que
  las copiadas son etiquetas **propias** (no las mismas de Casa 1) y sirven para clasificar, y
  las validaciones (misma categoría, tipos distintos y categorías de otro usuario).

## v1.29 — Recurrente u ocasional (y el saldo que no se movía)

Al crear un movimiento ahora se elige **«una sola vez» (ocasional)** o **«se repite»**. La
maquinaria ya existía —los gastos recurrentes **son** las suscripciones, con su job que los
genera—, pero obligaba a ir a otra pantalla y a teclear otra vez monto, categoría y etiqueta.

- **`POST /transacciones` acepta `recurrencia: {periodicidad}`**: crea el compromiso **en la
  misma operación** (atómica) y deja la transacción como el pago de *este* periodo, enlazada
  (`suscripcion_id` o `ingreso_recurrente_id`).
  - **El día sale de la fecha**: no hay que teclear día ni un segundo campo que pueda
    contradecir a la fecha. El compromiso apunta al **siguiente** periodo, así que el job
    **no duplica** el que acabas de registrar.
  - Nombre, monto, moneda, categoría, etiqueta, tarjeta y cuenta se heredan del propio
    movimiento.
  - Un gasto admite `semanal|mensual|trimestral|semestral|anual`; un ingreso
    `diario|semanal|mensual` (los ENUM no son iguales). Si no encaja, se avisa con las
    válidas. Una **transferencia recurrente** todavía no: el compromiso tendría que saber de
    qué cuenta sale y a cuál entra en cada periodo.
- **El hueco que apareció al probarlo**: las pólizas ya guardaban de qué cuenta sale el dinero,
  pero las **suscripciones** y los **ingresos recurrentes** no. Cada movimiento que generaba el
  job quedaba **sin cuenta**: aparecía como «movimiento sin cuenta» y **no movía ningún
  saldo** — justo lo contrario de «no volver a hacerlo mes a mes». Migración `0023`:
  `suscripciones.cuenta_id`, `ingresos_recurrentes.cuenta_id` y, para simetría con
  `suscripcion_id`, `transacciones.ingreso_recurrente_id` (que el ingreso generado también se
  pueda marcar). Los generadores pasan a rellenar la cuenta.
- **Hueco de aislamiento cerrado de paso**: al crear o editar un movimiento se podía apuntar a
  la **categoría, etiqueta, suscripción o póliza de otro usuario** (el movimiento era tuyo,
  pero el reporte mostraba su nombre). Ahora todas las referencias se validan con `get_owned`.
- **Un solo concepto visible**: el menú estrena el grupo **Recurrentes** con *Gastos
  recurrentes* (la ruta `/suscripciones` de siempre) e *Ingresos recurrentes*, y el formulario
  de transacción lleva a la misma idea. Llamar «Suscripciones» a un arriendo, un colegio o los
  servicios hacía que no se reconocieran como lo que son.
  - **Decisión**: la **tabla sigue llamándose `suscripciones`**. Renombrarla (y
    `transacciones.suscripcion_id`) es una migración cosmética que arrastra respaldo,
    recurrencia, alertas y frontend, sin ganancia funcional; queda documentado aquí y el
    nombre visible es el correcto.
- **UI**: en *Transacciones*, «Una sola vez (ocasional)» / «Se repite…» con la periodicidad
  según el tipo, y el listado marca con **🔁 recurrente** lo que viene de un compromiso. En
  las dos pantallas de recurrentes se elige **de qué cuenta sale** (o a cuál entra) el dinero.
- Tests: 62 en verde (antes 58). Cubren que el compromiso nazca con el día correcto y su
  cuenta, que el job **no duplique** el periodo ya registrado y **sí** genere el siguiente (con
  su cuenta, y que el saldo cuadre con los dos), el ingreso recurrente, y las validaciones
  (transferencia recurrente, periodicidad que no encaja y referencias de otro usuario → 404).

## v1.30 — Pagar la tarjeta (y la deuda que se contaba dos veces)

Pagar la tarjeta no tenía forma de registrarse: la deuda se actualizaba a mano («lo que dice el
extracto») y el dinero que salía de la cuenta había que anotarlo por separado. Y al mirarlo de
cerca apareció un **bug latente**: la deuda se calculaba **sumando** todos los extractos de la
misma moneda, así que registrar el de octubre además del de septiembre **duplicaba la deuda**.

La raíz de las dos cosas es la misma: **un nivel no se suma como un flujo**. El extracto es un
nivel («debes esto a esta fecha»); el pago es un flujo.

- **`POST /tarjetas/{id}/pagos`**: registra un pago que **baja el saldo de la cuenta y la deuda**
  a la vez, y devuelve la tarjeta ya actualizada. `DELETE /tarjetas/{id}/pagos/{pago_id}` lo
  deshace (quita el pago y su movimiento).
- **Deuda vigente = último extracto de cada moneda − pagos posteriores a su fecha**:
  - registrar un extracto nuevo **reemplaza** al anterior en vez de sumarse (el bug);
  - el pago baja la deuda hoy, y cuando llegue el extracto siguiente —que ya lo incluye— pasa a
    ser el nuevo nivel y el pago **deja de restarse**: no se cuenta dos veces ni al derecho ni
    al revés. (Un test lo fija: extracto 1.000.000 → pago 300.000 → extracto nuevo 800.000 →
    deuda 800.000.)
  - Un pago del **mismo día** del extracto cuenta como posterior. Es la única ambigüedad real
    del modelo y se resuelve hacia el lado útil: lo normal es pagar después de recibirlo, y a
    menudo el mismo día que lo registras en la app.
- **Pagar la tarjeta NO es un gasto**: se guarda como una **transferencia** de la cuenta a la
  tarjeta (se amplió la regla que escribí en la v1.27, que prohibía tarjeta en una
  transferencia: ahora el destino es **una** cuenta **o** una tarjeta de crédito). Queda fuera
  de los reportes por categoría y del flujo de caja, que es lo correcto: si fuera un gasto, el
  consumo se contaría **dos veces** (al comprar y al pagar). Un test lo comprueba: tras pagar,
  `gastos` del mes sigue en 0 y el desglose por categoría está vacío.
- **Límites con mensaje claro**: no se puede pagar más de lo que se debe en esa moneda (422 con
  la cifra), ni una tarjeta de **débito** (no genera deuda: su saldo es el de su cuenta), ni
  desde una cuenta de otra moneda, ni con datos de otro usuario (404).
- **UI**: botón *Pagar tarjeta* en *Tarjetas*, con el monto **ya puesto** en lo que se debe, el
  desglose a la vista (`extracto 1.000.000 − pagos 300.000 = 700.000`) y la lista de pagos con
  *deshacer*. En *Transacciones*, un pago se lee `🔄 Ahorros → 💳 Visa`.
- **Decisión de modelo**, y lo que **no** hice: la alternativa era llevar la deuda como
  *flujo* completo (deuda inicial + consumos − pagos). La descarté porque **reinterpreta los
  datos que ya tienes**: tus extractos registrados pasan a ser «saldo inicial» y los consumos
  con tarjeta que ya anotaste se **sumarían otra vez** (probablemente ya están en el extracto).
  Esta versión es **aditiva**: no migra ni reinterpreta nada y es reversible.
- Tests: 65 en verde (antes 62). Cubren el pago (cuenta y deuda a la vez, y que **no** sea
  gasto), el extracto nuevo con y sin pago previo, el extracto repetido, deshacer el pago, y
  los límites.

## v1.31 — `/health` que comprueba la base

`GET /health` respondía `{"status":"ok","app":"konta"}` **pasara lo que pasara**: con
PostgreSQL caído seguía diciendo `ok`. El `depends_on: service_healthy` de compose solo valida
al arrancar, así que un backend roto en marcha se veía verde y, peor, el frontend servía la web
sobre él.

- **`GET /health` consulta la base** (`SELECT 1`):
  - `200` → `{"status":"ok","app":"konta","base":"ok","error":null}`
  - `503` → `{"status":"error","app":"konta","base":"sin conexión","error":"OperationalError"}`
- **No filtra la cadena de conexión**: devuelve solo el **tipo** de excepción; el mensaje
  completo va al log. Un healthcheck suele quedar expuesto sin token, así que no es sitio para
  el DSN ni para la contraseña. (Comprobado: la respuesta no contiene ni host, ni base, ni
  usuario.)
- Sigue **sin pedir token** (lo consulta el orquestador, que no tiene credenciales).
- **`docker-compose.yml`**: `healthcheck` del backend con `python -c` + `urllib` (la imagen ya
  trae Python; así no depende de `curl`), con `start_period: 30s` para dar margen a las
  migraciones del arranque. Y el **frontend ahora espera a que el backend esté `healthy`**
  (`condition: service_healthy`) en vez de arrancar en cuanto el contenedor existe.
- Verificado **de punta a punta**, no solo con tests: con la base en pie el comando del
  healthcheck sale `0`; apuntando el backend a un puerto muerto devuelve `503` y el comando
  sale `1`, que es lo que hace que el contenedor pase a *unhealthy*.
- Tests: 68 en verde (antes 65). Cubren el `200` con la base en pie, el `503` con una sesión
  que falla (sin filtrar el detalle) y que sigue sin pedir token.

## v1.32 — Linter en CI (y lo que encontró)

No había ningún linter, así que un import muerto, una fecha sin zona horaria o un
`except` que se traga el error entraban sin que nadie los viera. Al pasar `ruff` salieron
**358 hallazgos**, de los que casi todos eran ruido (232 `B008` por `Depends(...)` en los
valores por defecto, que es la forma canónica de FastAPI). Esta versión deja la config
acotada a lo que **caza bugs** y arregla los hallazgos reales.

- **`[tool.ruff]` en `pyproject.toml`** con `select` explícito —nombres e imports muertos
  (F), orden de imports (I), sintaxis obsoleta (UP), trampas conocidas (B), `except` ciego
  (BLE), fechas sin zona (DTZ), simplificaciones (SIM) y `noqa` muertos (RUF100)— e
  **ignorados con motivo**: `B008` (FastAPI) y `FURB157` (`Decimal("0.00")` fija la escala
  exacta del dinero) y `SIM108` (a veces el `if`/`else` con su comentario se lee mejor que
  el ternario). El `select` explícito importa: el set por defecto de esta versión de ruff
  trae familias enteras que el proyecto no había elegido.
- **Hallazgos reales corregidos**:
  - **dos imports muertos** (`select` en `presupuestos.py` y `obtener_tasa` en
    `tarjetas.py`, que quedó sin uso al mover la deuda a `app/tarjetas.py`);
  - **un `date.today()`** en el validador de fecha de nacimiento: usaba la zona del
    servidor en vez de `recurrencia.hoy()` (`FINANZAS_TIMEZONE`), así que podía rechazar
    un nacimiento de hoy. Y **26 más en los tests**, que ahora usan el «hoy» de la app
    (importado como `hoy_app` porque hay tests con una variable local llamada `hoy`).
    Ojo: mi primer reemplazo dejó `hoy = hoy()` en esos sitios (una variable que se
    referencia a sí misma); el linter lo cazó con `F823` antes de que llegara a `main`.
  - **`main.py`: el catch-up del arranque se tragaba el error** con un `except: pass`.
    Ahora lo registra en el log y sigue arrancando.
  - **10 `raise` dentro de `except`** que perdían el error original: ahora encadenan
    (`from exc`) cuando el motivo es útil —fallos de red en monedas y notificaciones— y lo
    cortan (`from None`) cuando el detalle es interno y la API ya da su propio mensaje
    (token inválido, nombre duplicado, JSON de respaldo inválido).
  - **6 enums** pasan de `(str, enum.Enum)` a **`enum.StrEnum`** (Python 3.11+); además
    `str(miembro)` devuelve el valor y no `"TipoTransaccion.GASTO"`.
  - Un `zip()` sin `strict=` (las longitudes ya se validaban), un `if` anidado, una
    condición «yoda» en un test y un `strptime` sin zona que **sí** es correcto (solo se
    usa la fecha) quedan con `# noqa` y su motivo.
  - Los **8 `except Exception` deliberados** (embeddings opcionales, OCR con binarios
    externos, `decode_token`, respaldo, health, el arranque y un test que necesita permisos
    de base) llevan `# noqa: BLE001` **con la razón escrita al lado**: la regla sigue
    activa, así que un `except` ciego *nuevo* sí falla.
- **CI**: paso `ruff check .` antes de las migraciones y los tests (es lo más rápido y lo
  que mejor explica un fallo), y `ruff` añadido a las dependencias de desarrollo.
- Resultado: **`ruff check .` limpio** y 68 tests en verde.
- **El primer CI en rojo fue por mi culpa, no del linter**: `ruff --fix` también reordenó
  los imports de `alembic/` (24 archivos) y solo commiteé `app/`, `tests/` y
  `pyproject.toml`. En local pasaba porque los arreglos estaban en el árbol de trabajo, pero
  el CI parte del repo limpio. Queda anotado en el README: `git status` antes de subir y
  commitear todo lo que el linter haya tocado.

## v1.33 — Ver (y deshacer) lo que el OCR ha aprendido

El clasificador **aprende** de cada corrección: cuando cambias la etiqueta de una línea, se
guarda «este texto va aquí» (`reglas_ocr`) y ese es el **primer** nivel que mira al leer un
recibo — antes que el diccionario y que los embeddings. El problema es que era de **una sola
dirección**: la app aprendía de ti y no había forma de ver qué sabía, corregirlo ni deshacer un
aprendizaje equivocado. Y como el historial **manda sobre todo lo demás**, un aprendizaje malo
contaminaba todas las facturas siguientes sin manera de arreglarlo desde la app.

- **`GET/POST /reglas-ocr`** y **`GET/PATCH/DELETE /reglas-ocr/{id}`**: listar lo aprendido,
  enseñar una regla a mano, corregir el patrón o la etiqueta, y borrarla.
- El **patrón se normaliza igual que al aprender** (mayúsculas, sin acentos ni códigos), así
  que una regla escrita a mano empareja de verdad; si al normalizar queda vacío (un texto que
  solo tiene números y símbolos), se rechaza con un 422 en vez de guardar una regla inútil.
- **Unicidad por usuario**: un patrón repetido da `400` con el aviso de que la edite en vez de
  crear otra (la tabla ya tenía `uq_reglas_ocr_patron`; ahora no revienta con un 500).
- La respuesta incluye **dónde cae** la regla (`Categoría › Etiqueta`) y **cuántas veces la ha
  usado** el clasificador, para poder juzgar si está haciendo bien su trabajo.
- **UI**: nueva página *Reglas de OCR* (grupo **Herramientas**, con enlace desde *Facturas*)
  con buscador, corrección en línea y borrado. Explica que el historial manda sobre el
  diccionario, que es justo el motivo por el que conviene poder borrarlo.
- Tests: 70 en verde (antes 68). El interesante es de ida y vuelta: enseñar una regla →
  el recibo se clasifica por `historial` → **borrarla** → el mismo recibo deja de reconocerse;
  y corregirla → el mismo artículo cambia de etiqueta. Más duplicados, patrón vacío, etiquetas
  ajenas (404) y aislamiento entre usuarios.

## v1.34 — Un recibo: un gasto o un gasto por artículo

El OCR por línea crea **una transacción por artículo**, que es lo correcto para la tira del
súper (30 líneas, 30 cosas, cada una a su etiqueta) y un estorbo para una compra de dos o tres
cosas: el listado y los reportes se llenan de movimientos sueltos. Faltaba la otra forma de
cerrarlo.

- **`POST /facturas/{id}/confirmar-total`**: crea **una sola** transacción con el total y deja
  las líneas como **detalle** (todas enlazadas a esa transacción, y `factura.transaccion_id`
  apuntando a ella). El detalle no se pierde: sigue en la tabla y en la base.
- **El total**: si no se indica `monto`, es la **suma de las líneas pendientes** —lo que ves en
  la tabla, no lo que el OCR creyó leer—. Y `monto` permite forzar el total del recibo cuando
  el detectado difiere (la UI ofrece «usar el total del recibo (X)» con un clic).
- **Descripción**: `descripcion` si la das; si no, el nombre del artículo cuando es uno solo, o
  «Compra de N artículos». Antes esto no existía y una compra de tres cosas quedaba como tres
  movimientos sin relación entre sí.
- La **categoría sale del respaldo** (`etiqueta_id` o `categoria_id`): al ser un solo gasto no
  hay una etiqueta por línea que heredar. Sin respaldo el gasto queda sin categoría, así que la
  UI ya lo pide en el mismo bloque.
- Se conservan las reglas del flujo por línea: de dónde sale el dinero (tarjeta de **débito**
  hereda su cuenta), la fecha, el aislamiento por usuario (404) y «no hay líneas pendientes»
  (400) al repetirlo.
- **De paso, un refactor con red**: el contexto de pago (cuenta, tarjeta, fecha y respaldo) se
  factorizó en `_contexto_de_pago` para no duplicarlo entre las dos formas de confirmar. Al
  hacerlo, el decorador `@router.post("/confirmar")` quedó pegado a la clase auxiliar y FastAPI
  la registró como endpoint (pedía sus parámetros como *query*). **Lo cazaron cuatro tests que
  ya existían**, no la revisión: por eso conviene refactorizar con la suite delante.
- Tests: 72 en verde (antes 70). El nuevo comprueba que sea **una** transacción con el total,
  que las tres líneas apunten a ella, el monto forzado, la descripción propuesta, el aislamiento
  y que la cuenta se descuente **una sola vez**.

## v1.35 — Limpieza de datos y el ENUM, resuelto (no era un resto)

Antes de dar el proyecto por cerrado, una revisión de **qué datos hay de verdad** y de si
queda algo sucio que sea mejor arreglar ahora que con datos reales dentro.

### Los datos: solo había basura mía

En el servidor de desarrollo había **16 bases**: las dos del Sistema de Contexto (`contexto`,
`contexto_test`) y **14 `konta_*` que fui creando yo** en las rondas de verificación (una por
prueba: migraciones, transferencias, pagos, linter, 0012, CI…). Ninguna la referencia el
proyecto —la app apunta a `localhost:5433/finanzas` (el PostgreSQL de `docker-compose`) y el
RAG a `contexto`— y ninguna tenía datos que no fueran de prueba. **Borradas las 14.** Queda una
sola `konta_test` para poder correr la suite.

Y de los valores «dudosos» en toda la base: **1 póliza semestral** (de prueba) y **0
transferencias**.

### El ENUM no era un resto, era una función

La nota decía que `periodicidad.semestral` «se queda aunque se baje la `0019`». Al ir a
quitarlo apareció lo importante: **`semestral` es una función viva**. Lo cubren cuatro tests
(el peso mensual de una prima semestral es 1/6, «dos primas en 12 meses, no doce»), está en las
opciones de *Pólizas* y de los recurrentes en *Transacciones*, y se explica en *Reportes*.
Quitarlo habría sido borrar las pólizas y suscripciones semestrales —que en Colombia son de lo
más común— a cambio de una simetría cosmética en el camino de rollback.

**Decisión: se queda**, y ahora está escrito donde toca:
- el `downgrade` de `0019` lleva la **receta verificada** por si algún día hace falta (quitar
  los `DEFAULT` primero, migrar las filas después, recrear el tipo…), con sus dos trampas
  reales y el aviso de que la conversión de datos es una decisión **de datos**, no técnica;
- `0022` remite a esa receta (el mismo caso con `transferencia`).

### Lo que sí era un hueco: nadie vigilaba la deriva de los ENUM

Al probar la receta se descubrió que **`alembic check` no compara las etiquetas de un ENUM**
(con el tipo recreado sin `semestral`, seguía diciendo que no había deriva). Es decir: un valor
que exista en el código y no en la base —o al revés— pasaba el CI y fallaba en producción, al
insertar justo esa fila.

- **Nuevo test** `test_los_enums_de_la_base_coinciden_con_los_del_codigo`: compara las etiquetas
  de los seis ENUM (`tipo_categoria`, `periodicidad`, `estado_suscripcion`, `tipo_tarjeta`,
  `tipo_transaccion`, `periodicidad_ingreso`) entre la base y los enums de Python, y dice cuál
  sobra y de qué lado. Comprobado que **detecta** una deriva real (`solo en el código
  ['semestral']`), no solo que pasa cuando todo está bien.
- Con esto, la sección *Pendiente / ideas* se queda con **una** entrada: los dos huecos de UI.
- Tests: 73 en verde (antes 72).

## v1.36 — El parseo de dinero estaba corrompiendo datos (Fase 0 de extractos)

Antes de construir la lectura de extractos revisé el parseo de dinero, porque todo el valor
de esa función depende de leer bien cada cifra. Había **tres copias** del parser (en
`facturas`, `importacion` y `lineas`) y **solo la de `lineas`** entendía el formato
colombiano. Las otras dos, que son las que usan el importador de CSV y la detección del total
de una factura, estaban corrompiendo datos **en silencio**:

| Entrada | Antes | Ahora |
|---|---|---|
| `44.900` | **44,9** | 44.900 |
| `1.500.000` | **`None` → la fila se descartaba** | 1.500.000 |
| `450.000` | **450** | 450.000 |
| `(120.000)` | **-120** | -120.000 |
| `44.900-` (signo al final) | **44,9** (perdía el signo) | -44.900 |
| `$ 5.32 2 ,2 0` (espacios dentro) | fallaba | 5.322,20 |
| `$9.568,71$9.568,71` (duplicado) | fallaba | 9.568,71 |

Y en una factura con `SUBTOTAL 22.616` y `TOTAL 25.116`, el **total detectado** salía
`22.616`: la expresión regular buscaba `total` sin límite de palabra, así que casaba con
**«SUBTOTAL»**. Sobrevivió porque ningún test comprobaba el *valor* de `monto_detectado`,
solo que no fuera `None`.

- **`dinero.py`**: un solo parser, con `parsear_monto` (valor estricto), `buscar_montos`
  (extraer valores de una línea), `detectar_formato` y `quitar_duplicado`.
  - **Formato del documento inferido**: `44.900` es ambiguo (44.900 en Colombia, 44,9 en
    EE. UU.) y lo decide el conjunto de cifras del archivo. Las tres hojas reales
    (Davivienda, Amex en pesos y CMR) se detectan como colombianas, que es lo correcto.
  - Regla de los dos separadores: **el último es el decimal** (`956,315.00` → 956.315;
    `8.780.590,00` → 8.780.590), así conviven los dos formatos en el mismo archivo.
  - Signos en las tres formas que usan los bancos (delante, detrás y paréntesis).
- **Los tres sitios ahora usan el mismo parser** (`facturas`, `importacion` y `lineas`
  delegan en `dinero.py`): se borran dos copias del parser roto.
- **`detectar_monto` arreglado**: `\btotal\b` no casa dentro de `SUBTOTAL`, y se toma el
  último total (el de después de subtotal e impuestos). Comprobado con el recibo de prueba:
  **25.116** en vez de 22.616.
- **Un límite que se dice en voz alta**: cuando el PDF **pega** dos valores sin separador
  (`$108.515,3125,87` = pesos + dólares), no hay forma de partirlos por texto. `buscar_montos`
  es conservador (nunca inventa céntimos partiendo un número pegado) y el aviso de que eso se
  resuelve **parseando por columnas** está en el código y en un test.
- Tests: **113 en verde** (antes 72). `tests/test_dinero.py` es una tabla con los formatos
  reales de los tres extractos y del recibo, incluidos los tres pagos cuadrados al centavo
  (Davivienda 5.195.786,83 · Amex 8.780.589,32 · CMR 571.527,30). Y dos tests de regresión en
  los puntos de uso: el CSV colombiano (que ya no pierde filas) y el valor de `monto_detectado`.

## v1.37 — Extractos bancarios, Fase 1: el motor de lectura (en progreso)

Primera mitad de la Fase 1: **leer** un extracto (PDF o Excel, tarjeta o cuenta) y
**conciliarlo** contra las cifras que el propio banco declara. Falta la API y el panel, que
van en el siguiente tramo.

- **Tablas nuevas** (migración `0025`): `extractos` (periodo, corte, pago, cupo, desglose del
  corte, resultado de la conciliación y el texto leído) y `extracto_movimientos` (fecha,
  descripción, valor con signo, moneda, saldo, cuotas, cuota del mes, valor pendiente,
  **monto original y tasa de cambio** cuando la compra fue en divisa, y el tipo deducido).
  `tipo` y `formato` son texto validado en Python y **no** ENUM de PostgreSQL: son listas que
  crecerán y quitar un valor de un ENUM no existe (la lección del `0019`).
- **El motor** (`extractos.py`) lee tres extractos reales, y en dos de ellos **cuadra al
  centavo**:
  - **Davivienda (PDF con contraseña)**: compras **1.004.353,02** ✅, pagos **1.103.790,03** ✅,
    pago total **5.195.786,83** ✅ y **48/48** filas con su aritmética correcta.
  - **Amex (Excel de dos monedas en dos hojas)**: compras **123.797,00** ✅, abonos
    **974.993,00** ✅, pago total **8.780.589,32** vs 8.780.590,00 (el banco lo redondea) ✅,
    **20/20** filas ✅.
  - **CMR (PDF)**: lee los 30 movimientos y valida 30/30 filas, pero su conciliación todavía
    no cuadra (imprime los pagos en positivo y llama «consumos del mes» al capital facturado).
- **Lo que enseña cada archivo, y que está en el código**:
  - **PDF por coordenadas, no por líneas**: `(y, x)` separa las columnas y desaparecen los
    pegotes (`$108.515,3125,87`), los valores duplicados (`$9.568,71$9.568,71`) y las
    etiquetas partidas (`Núme ro`). El encabezado se busca por **banda de `y`** y las columnas
    salen de las posiciones del propio encabezado, así que el mismo código sirve para bancos
    distintos.
  - **La dirección del eje `y` no es la misma en todos los PDF**: en el CMR crece hacia abajo
    y en Davivienda hacia arriba. Se deduce de las fechas.
  - **Un movimiento puede ocupar varias líneas** y la tabla **continúa en la página siguiente
    sin repetir el encabezado**: se reutilizan las columnas ya deducidas.
  - **La conciliación tiene dos niveles**: por componentes (con tolerancia, porque el banco
    redondea el total) y **por fila** (`pendiente = cuota × cuotas que faltan`), que detecta un
    renglón mal leído aunque los totales cuadren.
  - **Lo anterior al periodo no es un gasto nuevo**: son compras diferidas de meses atrás.
- **Errores propios que cazaron los datos y los tests**: `campo_de("efectiva")` devolvía
  «fecha» (el sinónimo `FEC`), las claves de meses estaban en minúscula mientras el texto se
  normaliza a mayúsculas (por eso el periodo no se detectaba), `MOVISTAR PAGOSEPAYCO` se
  clasificaba como pago (ahora el tipo usa límites de palabra) y el «Saldo anterior» del
  cashback ganaba al «Saldo periodo anterior».
- Tests: **136 en verde** (antes 113). `tests/test_extractos.py` cubre las piezas puras
  (tipo de movimiento, cuotas pegadas a la tasa, fechas sin año), la conciliación de los dos
  niveles y un **Excel de punta a punta construido en el test** (dos monedas, dos tablas,
  cuotas), porque los extractos reales no se versionan.

## v1.38 — Extractos, Fase 1 completa: API y panel

Segunda mitad de la Fase 1. Ya se puede **subir un extracto desde la interfaz**, ver si los
números cuadran y leer el análisis.

- **API** (`/extractos`): subir (PDF con contraseña o Excel), listar, ver el detalle, borrar y
  `…/analisis`. Al subir se lee, se clasifica cada compra con el mismo motor del OCR
  (`historial → diccionario → embeddings`) y **no se crea ninguna transacción**: eso es la
  Fase 2, y solo después de que la conciliación cuadre.
- **Panel** (página *Extractos*, en *Herramientas*): subida con contraseña y tipo (tarjeta o
  cuenta), lista de extractos con su semáforo («cuadra» / «revisar»), y el análisis:
  - **¿Cuadra con lo que dice el banco?** los controles uno por uno, con lo calculado, lo que
    declara el extracto y la diferencia; y el detalle de los movimientos dudosos.
  - Tarjetas de **compras del periodo**, pagos, **costo del dinero** (intereses + comisiones),
    pago total y mínimo, **cupo utilizado** (con el % del cupo) e intereses declarados.
  - **A dónde se fue la plata** por categoría, **por moneda** y **compromiso futuro** (capital
    de las compras a cuotas).
  - Tabla de movimientos con tipo, cuotas, cuota del mes, pendiente, la compra en dólares con su
    tasa, y casilla para ver u ocultar lo anterior al periodo.
- **La invariante por fila estaba mintiendo y se arregló**: daba ✅ **sin validar ninguna fila**
  (bastaba con que no hubiera filas que validar). Ahora devuelve «sin datos» y lo avisa.
  - Y al mirar la fila que marcaba, resultó que **el banco es incoherente consigo mismo**: la
    cuota **incluye intereses** y el pendiente es **capital**. El control se reformuló con esa
    regla del dominio (`pendiente / cuotas que faltan ≤ cuota ≤ 2,5 ×`), así que una compra con
    intereses ya no se marca como error, pero una columna mal leída sí.
  - Al ampliar la detección de columnas apareció otra: **el Excel escribe las cuotas `1/1`** y
    solo se aceptaba `1 de 1`.
- **La moneda se dice como es**: los totales van en la moneda del extracto, con el desglose por
  moneda al lado. El selector «ver en USD» se quitó porque **no convertía**: mostrar pesos con
  símbolo de dólares es peor que no ofrecerlo. Convertir necesita la tasa de cada compra, y las
  que no la traen salen listadas como `sin_tasa` en vez de inventarla.
- **Cómo se decide qué es de este mes**: el periodo se lee del extracto (`Desde/Hasta` o «Periodo
  facturado»), con dos guardas nuevas: un rótulo como *«Movimientos durante el periodo»* no es la
  etiqueta del periodo, y un periodo con las fechas al revés se **descarta** (un periodo falso
  marcaría todo el detalle como de meses anteriores, que es justo lo que no hay que hacer).
- Tests: **142 en verde** (antes 136). Incluyen la API de punta a punta (subir el Excel
  construido en el test, analizarlo, borrarlo, y que un usuario no vea los extractos de otro), el
  PDF **con contraseña** (sin ella 400, con ella se lee) y la regla de la cuota con intereses.
- Estado de los tres extractos reales: **Davivienda (PDF cifrado) y Amex (Excel de dos monedas)
  cuadran todos los controles**; el CMR (PDF) lee sus 30 movimientos pero su conciliación todavía
  no cuadra: imprime los pagos en positivo y llama «consumos del mes» al capital facturado. Queda
  como tarea propia.

## v1.39 — Extractos, Fase 2: importar los movimientos

Ya se puede pasar del análisis a las cuentas: **Importar a Konta** desde la misma página. Las
reglas son las que decidiste, y cada una tiene su test.

| Qué | Cómo se decide |
|---|---|
| Se importa | Lo que te facturan **este** mes: cada compra (**por la cuota del mes** si es a cuotas), intereses y comisiones |
| También entra | La **cuota de este mes** de las compras de meses anteriores: es plata que sale ahora |
| No se importa | El **valor completo** de una compra de meses anteriores (ya se contó al comprarla), los **ajustes** y los **pagos** |
| Si falta la cuota del mes | La fila **no** se importa y se dice por qué: ni el valor completo (inflaría el mes) ni la mitad |
| Si se importa dos veces | Nada se duplica: el movimiento ya importado se salta y lo dice |

- **La prueba de que la semántica es la correcta**: lo que se importa **cuadra con el pago
  mínimo del corte** en los dos extractos reales.
  - **Davivienda**: 84.877,19 (cuotas de las compras del periodo) + 170.575,21 (cuotas de
    compras anteriores) + 97.624,49 (intereses del corte) = **353.076,89, el pago mínimo
    exacto**. Y los intereses de Davivienda **no** vienen en su tabla de movimientos: se añaden
    desde la cifra que declara el corte (si vinieran como movimiento, como en Amex, no se
    añadirían para no contarlos dos veces).
  - **Amex**: **956.314,13** frente al pago mínimo declarado 956.315,00 (el banco redondea).
- **Dos errores de clasificación que aparecieron al cuadrar el mes** (y que costaban dinero):
  - `MERCADO PAGO*ROMEOKIDS` se clasificaba como **pago** por llevar «PAGO» dentro: es un
    comercio. Seis filas así se saltaban **20.206,28** de cuotas del mes. Ahora las pasarelas
    (`MERCADO PAGO`, `PAGOSEPAYCO`, `PAYU`, `WOMPI`, `EPAYCO`…) son compras, y «pago» solo
    cuando lo es de verdad (`PAGO TARJETA`, `PAGOS POR PSE`, `ABONO`, `CANCELACION`…).
  - Los patrones buscaban en el texto **con espacios**, y el extracto de CMR escribe
    `PAG O TARJETA C MR`: ahora se buscan las dos formas (con espacios y sin ellos).
- **La decisión del corte, aplicada**: el **cupo utilizado** se registra como **deuda** de la
  tarjeta (es un nivel por moneda, justo lo que ya modelaba `DeudaTarjeta`) y el **pago total**
  pasa a las **alertas** con la **fecha límite que dice el extracto**, en vez de la fecha
  estimada por el día de pago configurado.
- **En la interfaz**: previsualización con lo que se importa, lo que se omite y el porqué, la
  comparación con el pago mínimo, una casilla para incluir o no las cuotas anteriores
  (por defecto sí, que es lo que pagas), el semáforo de «importado» en cada fila y el aviso de
  cuántas transacciones se crearon.
- Tests: **156 en verde** (antes 142), con las reglas una por una y la importación de punta a
  punta: importar, no duplicar al pulsar otra vez, la deuda registrada y la alerta con el pago
  total del extracto.

## v1.40 — Extractos, Fase 3: detectar recurrentes y suscripciones

Debajo del análisis, Konta propone lo que **se repite todos los meses**, con la evidencia de
cada uno y su confianza. Cinco señales, de la más fuerte a la más débil:

| Señal | Confianza | Por qué |
|---|---|---|
| **Repetición entre cortes** (mismo comercio, ~1 mes, monto parecido) | **alta** | Es lo que define una suscripción |
| **Ya estaba en tus movimientos** | alta/media | Lo llevabas pagando de antes: sirve aunque solo tengas un extracto leído |
| **Diccionario de servicios** (Netflix, Spotify, Prime Video, iCloud, ChatGPT…) | media | Un servicio **nuevo** aparece **una sola vez** en su primer extracto: sin esta señal no se vería nunca |
| **Compra a cuotas** | — | **Nunca** se propone. En un extracto real RAPPI aparece 7 veces y no es una suscripción: es una compra a 24 cuotas |
| **Diferida por el banco** | media | Amex difiere AUDIBLE a 36 cuotas de 0,29 USD: se propone **con la cuota** como monto y diciendo por qué |

- **Dos cargos del mismo servicio el mismo día son dos planes**: PRIME VIDEO 17.999 y 4.999
  salen como dos candidatos, no como una suscripción de 22.998. Los montos que difieren más de
  un 20 % se separan.
- **Nada se inventa**: ni pagos, ni intereses, ni comisiones, ni impuestos. El próximo pago se
  calcula con la periodicidad deducida de los cargos reales (semanal/mensual/trimestral…).
- **Crear es idempotente**: se eligen candidatos por su clave, el servidor los crea **desde sus
  propios datos** (nunca desde importes que mande el cliente), hereda la tarjeta o la cuenta del
  extracto y **omite** los que ya existían con ese nombre.
- **Comprobado con los extractos reales**: de Davivienda sale Netflix (44.900); de Amex salen
  Microsoft 365 (45.999), Seguro Cardif (29.900), dos planes de Prime Video y Audible (0,29 USD
  al mes, con el aviso de que está diferido). Netflix se detectó **cruzando los dos extractos**.
  Y RAPPI, con sus 7 apariciones a 24 cuotas, **no** aparece entre los candidatos.
- Tests: **165 en verde** (antes 156), con cada señal por separado, la creación y que no se
  duplique.

## v1.41 — Extractos, Fase 4: valor acumulado (última fase)

Página nueva **Deuda y cuotas** (junto a Extractos), que mira **todos** los extractos juntos y
responde las tres preguntas que uno se hace de verdad.

- **Compromiso futuro**: lo que ya compraste a cuotas y falta pagar — capital pendiente, cuota
  de este mes y el **calendario mes a mes** (6/12/24 meses), **por moneda** y sin convertir. Más
  la tabla compra por compra: valor, cuota, cuántas van, cuántas faltan, pendiente y tasa.
  - Se queda con el **último estado de cada compra** (la identidad es descripción + valor +
    **fecha de compra**, que es la que no cambia entre cortes): tener dos extractos no cuenta el
    capital dos veces.
- **La tasa real, que hasta ahora se leía y se tiraba**: el extracto trae la de cada compra
  (`1,9648% 26,30%` = mensual y anual) y ahora se guarda (migración `0026`). La tasa de la deuda
  es el **promedio ponderado por capital pendiente** —la deuda cara pesa más—, y si el extracto
  no la trae se usa la de la tarjeta **diciendo que es esa**. Comprobado con los reales:
  Davivienda da **27,44 % E.A. ponderada** y Amex **24,70 %**.
  - Leerla tuvo su detalle: en Excel viene con **cuatro decimales** (`29.2215`), que el parser de
    dinero rechaza porque el dinero no tiene más de dos. Las tasas tienen su propio lector.
- **Simulador con la tasa real**: cuántos meses y cuántos intereses, y avisa cuando el pago **no
  cubre los intereses** (la deuda nunca baja). Con el extracto de Davivienda: 32 meses y
  **1.762.962,14 de intereses** pagando la cuota actual.
- **Costo del dinero**: intereses + comisiones + impuestos por extracto y su **porcentaje del
  pago**. En Amex: 207.560,42 = **21,7 %** de lo que paga.
- **Auditoría extracto ↔ Konta** con las mismas reglas que la importación: lo que se importa
  contra el **pago mínimo del corte** (✅ en Amex: 956.314,13 frente a 956.315,00), si falta algo
  por importar (distinguiendo los pagos, que **no** se importan), si hay movimientos repetidos en
  el periodo que no vengan del extracto, la conciliación del banco y el cupo utilizado contra el
  capital pendiente.
- Tests: **173 en verde** (antes 165): proyección por moneda, el último corte manda, la tasa
  ponderada, el respaldo a la tasa de la tarjeta, el pago que no alcanza, el costo del dinero y
  la auditoría (incluido el movimiento metido a mano).

### v1.41.1 — Los totales ignoraban las compras en dólares

Cierre de un cabo suelto de la decisión multi-moneda: el total en la moneda del extracto **no
incluía** los movimientos en otra moneda (los dejaba solo en el desglose). Ahora se convierten
con **la tasa que trae el propio extracto** —la del día de la compra, no una de hoy— y lo que
**no** trae tasa no se convierte: se queda fuera del total, se cuenta aparte en `sin_tasa_total`
y se avisa. En el extracto CMR de prueba, las compras en COP pasan de 252.333,63 a
**335.017,81** al incorporar las de dólares con su T.C.

Tests: **174 en verde**.

## v1.42 — Cerrar los huecos de UI: borrar un aporte y editar o borrar un producto

Los endpoints ya existían (`DELETE /metas/aportes/{id}`, `PATCH` y `DELETE /productos/{id}`);
lo que faltaba era poder usarlos desde la interfaz.

- **Metas**: botón **Ver aportes** en cada meta (la lista se pide al abrirla, no con la lista
  entera) con fecha, monto y nota de cada aporte, y **Borrar** en cada uno. Al borrar se
  recarga la meta, así que el saldo baja de verdad y no solo en pantalla.
- **Mercado**: cada producto de la lista tiene **Precios**, **Editar** (abre la fila con su
  nombre y su unidad) y **Borrar**, que se lleva por delante sus precios y limpia la selección
  del comparativo si era el elegido. Antes solo se podía crear.
- Tests de los endpoints que ya existían y **no estaban cubiertos**: borrar un aporte hace
  bajar el saldo de la meta (no es un borrado visual) y un aporte ajeno devuelve 404; editar el
  nombre y la unidad de un producto, borrarlo con sus precios, y que un producto ajeno no se
  pueda tocar (404 en `PATCH` y en `DELETE`).
- Tests: **176 en verde** (antes 174).

## v1.43 — Facturas de caja grande: se leen enteras y se etiquetan solas

Salió de una factura real de supermercado (120 artículos) que llegaba incompleta y sin
etiquetas. Eran cuatro errores encadenados, y el tercero era el peor.

- **El dinero se leía 1.000 veces más pequeño.** Esa caja imprime `24,674` (veinticuatro mil
  seiscientos setenta y cuatro) en vez del `24.674` de siempre, y el detector de formato no lo
  veía: la coma con grupos de tres dígitos no contaba como prueba de nada. Ahora sí, así que
  `24,674` es 24674 y la cantidad `1.372 kg` sigue siendo decimal (son cosas distintas y ahora
  se leen distinto).
- **Se colaban líneas que no son artículos y se perdían otros.** `Tel: 4850175 Ext` y
  `TPV : TPV008SP012` entraban como artículos (con totales absurdos) y las líneas con marca de
  descuento (`6,375* D`) no casaban, así que el artículo se perdía: eran 89 de 120. Ahora hay un
  **modo factura numerada** que se apoya en lo que ese formato cumple: los artículos van
  numerados en orden (1, 2, 3…), cada uno trae su línea de valores (aunque la referencia sea un
  código de promoción, `COVA-00`) y la tabla termina en el `T O T A L`.
  - Resultado con la factura real: **120 artículos (los 120 que declara el documento)**, la
    **suma de las líneas = el TOTAL de la factura (1.188.248)** y el **monto detectado =
    1.188.248** (antes decía 120, que era el número de artículos).
- **Los artículos no se etiquetaban.** El diccionario no conocía `PERNIL`, `MARGARINA`, `UVA`,
  `SANDIA`, `COLIFLOR`, `KIWI`, `REPOLLITA`, `SAZONADOR`, `DESMAN`, `T.H`… y había un fallo de
  fondo: la palabra clave se busca **completa**, así que `YOGUR` no casaba con `YOGURT`. Además
  gana la palabra **más larga**, lo que aproveché para casos que estaban mal: `SALSA ... DE
  TOMATE` es despensa (no verdura), `CEBOLLA ... EN POLVO` también, y `PEPINO RES` es carne.
  - Con la factura real: **120 de 120 artículos etiquetados (100 %)**, antes 74 de 117.
- **Un bug de cantidades**: `4.00 un` se leía como **400 unidades** (con unidad de cuenta, el
  punto se tomaba por separador de miles). Dos decimales tras el punto son decimales siempre.
- Tests: **182 en verde** (antes 174), en `tests/test_lineas_factura.py`, con una factura
  sintética del mismo formato (`COVA-00`, marca `D`, `T O T A L` con letras separadas) y 21
  descripciones reales de supermercado comprobando su etiqueta.

### v1.43.1 — «Ver texto extraído» cortaba en 1.500 caracteres

El texto de una factura se mostraba **recortado a 1.500 caracteres** (el 16 % de los 9.577 de
una factura real), así que parecía que el OCR solo había leído hasta el artículo 17. El
problema no era la lectura —la tabla de líneas ya mostraba los **120 artículos**— sino esa
vista. Ahora:

- se muestra el **texto completo**, en un recuadro con scroll;
- el resumen dice **cuántos caracteres** trae (para que se vea que no falta nada);
- botón **Copiar todo**, porque el texto se estaba copiando a mano.

## v1.44 — Que las etiquetas se completen solas, y buscador en el desplegable

Salió de una factura real en producción: quesos, leche y yogures salían **«sin clasificar»**.
La causa no era el diccionario, y el diagnóstico costó mirar la base de datos del usuario.

- **La causa real**: el clasificador empareja sus palabras clave contra **nombres de
  etiquetas**, y a esa cuenta le faltaban `Lácteos y huevos` y `Cuidado personal` (se creó
  antes de que existieran). Sin ellas, ninguna palabra de lácteos podía casar: **13 de sus 16
  líneas sin etiqueta eran lácteos** y 3 de cuidado personal. Y de paso explicaba dos que
  estaban **mal** puestas: `YOGURT ALPINA*106ml CEREAL` y `MARGARINA CAMPI*250g C/SAL` caían
  en Despensa porque, al no existir Lácteos, ganaba otra palabra.
- **Se completan solas**: al leer las líneas de una factura, la app crea las etiquetas del
  diccionario que falten (idempotente: solo lo que no está, y respeta categorías renombradas
  o borradas). Antes había un botón para hacerlo a mano y, si no lo pulsabas, no te enterabas:
  eso era un fallo de diseño.
- **Migración `0027`**: completa esas etiquetas en **todas** las cuentas que ya existen, sin
  esperar a que el usuario abra nada.
- **Diccionario ampliado con los productos reales**: `BONYURT`, marcas (`VITAD`, `PARMALAT`,
  `YOPLAIT`, `ALQUERIA`, `COLANTA`, `ALPINA`), más quesos (`DOBLE CREMA`, `QUESO PERA`,
  `CRIOLLO`, `CREMOSINO`), `CREMA DE LECHE`. La **avena líquida** pasa a Lácteos y las
  **hojuelas** se quedan en Despensa por la palabra `HOJUELAS`, que es más larga y gana.
- **Tres correcciones finas que salieron de probarlo con sus datos**:
  - `TOSTAOS BIMBO*...MANTEQUILLA` es un paquete de galletas: la frase completa gana a
    `MANTEQUILLA`, que se lo llevaba a Lácteos.
  - `AREPAS ... QUESO` es una arepa: `AREPAS` y `AREPA DE` ganan a `QUESO`.
  - **Un bug de verdad en el parser**: `IGNORAR` buscaba por **subcadena** y `PARMESANO`
    contiene `MESA`, así que el queso parmesano **se caía de la factura** como si fuera una
    línea de restaurante. Ahora se busca por palabra completa. También apareció un test
    dependiente de la fecha (solo pasaba hasta el día 28) y se corrigió.
- **Buscador en el desplegable de etiquetas** (`SelectBuscable`): con 40 etiquetas, recorrer
  la lista con el ojo era tedioso. Ahora escribes y filtra al instante, buscando por etiqueta
  **o por categoría**, sin importar acentos ni mayúsculas, con teclado (↑ ↓ Enter Esc) y en
  los dos sitios donde se elige etiqueta (cada línea y «aplicar a todas»).
- Tests: **185 en verde** (antes 182), con los **16 productos reales** de esa cuenta como
  casos, el auto-sembrado (borrar la etiqueta y ver que se recrea y clasifica) y la coherencia
  entre el diccionario y las etiquetas que la app siembra.

## v1.45 — Etiquetas nuevas, y el selector deja de contradecirse

Segunda vuelta sobre el etiquetado de facturas, con lo que salió al mirar la pantalla real.

- **Etiquetas nuevas** (con sus palabras en el diccionario, que si no no clasifican nada):
  **Bebidas** (jugos, gaseosas, agua, cerveza, vino, energizantes, té),
  **Panadería** (pan, arepas, buñuelos, almojábanas, tortas),
  **Snacks** (mecato, papas fritas, chocolatinas, chicles) y
  **Congelados** (helados, nuggets, congelados). Antes todo eso caía revuelto en Despensa.
  - **Mascotas**: la categoría y sus etiquetas ya existían pero **sin ninguna palabra** en el
    diccionario, así que un concentrado no se podía clasificar. Ahora `Alimento` reconoce
    Purina, Dogourmet, Pedigree, Whiskas, Pro Plan… y `Veterinario` su clínica.
  - Palabras **específicas a propósito**: `PAPA FRITA` y no `PAPAS`, porque gana la más larga
    y con `PAPAS` a secas las papas del mercado se irían a Snacks. Hay test de eso.
  - Migración `0028` para crearlas en las cuentas que ya existen.
- **El selector deja de contradecirse** (el bug que se veía en la captura): una fila decía
  **«Sin etiqueta»** y a la derecha el badge decía **«diccionario»**. Pasaba porque al leer las
  líneas el servidor **crea etiquetas** y la página **no recargaba la lista**: el selector no
  encontraba el id y caía en «Sin etiqueta» mientras el badge decía la verdad.
  - Ahora la lista de etiquetas se **recarga después de leer** (y al sembrar el diccionario).
  - El badge de origen: **sin etiqueta ⇒ siempre ámbar «sin clasificar»**, nunca azul.
  - Y el buscador **no miente**: si el id no está entre las opciones, dice «(etiqueta no
    cargada)» en ámbar en vez de fingir que no tiene etiqueta.
- **Se acabó el «recarga forzada» al desplegar**: `nginx.conf` manda `Cache-Control: no-cache`
  para el `index.html` y cache largo solo para los `/assets/` (que llevan el hash en el
  nombre). El navegador estaba sirviendo el bundle viejo y parecía que el despliegue no llegó.
- **Un falso positivo que cazaron los tests**: puse `AROMATICA` en Bebidas (por la aromática,
  el té) y una **«VELA AROMATICA» se iba a bebidas**. Fuera: el té se cubre con `TE ` y
  `TE VERDE`, que no chocan con nada. Queda un test que lo vigila.
- Tests: **187 en verde** (antes 185), incluidos los productos que **no** se pueden robar
  (`PAPAS A GRANEL` sigue en Frutas, `VELA AROMATICA` no es una bebida).

### v1.45.1 — El café Águila Roja no es una cerveza

Al aplicar las etiquetas nuevas a los datos reales salió un tercer choque de marcas: había
puesto `AGUILA` en Bebidas (la cerveza) y **`CAFE AGUILA ROJA` se fue a bebidas**. Se
arregla con la frase completa (`AGUILA ROJA` → Despensa), que es más larga y gana, así que
el café vuelve a Despensa y la cerveza sigue en Bebidas. Con su test.

Tests: **188 en verde**.

### v1.45.2 — El 502 al desplegar: nginx se quedaba con la IP vieja del backend

Después de un despliegue, el portal cargaba (el HTML es estático) pero **toda la API devolvía
502** y parecía que el servicio estaba caído. En el log del frontend estaba la pista:

```
connect() failed (113: Host is unreachable) while connecting to upstream,
upstream: "http://10.89.3.76:8000/facturas"   ← una IP que ya no existía
```

**Causa**: nginx resuelve el nombre `backend` **una sola vez, al arrancar**, y se queda con esa
IP. Al recrear el contenedor del backend (cada despliegue) cambia de IP → nginx apunta a un
contenedor muerto. Yo recreé el frontend *antes* que el backend, así que quedó con la IP
anterior.

**Arreglo**: nginx ahora **re-resuelve** el backend cada 10 segundos (`resolver` + variable en
`proxy_pass`), así que recrear el backend ya no rompe nada. **Verificado de verdad**: recreé el
backend (IP nueva) y el proxy siguió respondiendo 200 sin tocar el frontend.

De paso, el orden correcto de un despliegue es **backend primero y frontend después**.

## v1.46 — Una compra = un movimiento (se acabó el listado de 120 filas)

El problema salió del uso real: un mercado de 120 artículos, confirmado **línea por línea**,
llenaba el listado de Transacciones con 120 filas y volvía tedioso encontrar cualquier cosa.
La culpa era del diseño: la acción principal de la factura era «Confirmar N línea(s)» y la
opción de un solo movimiento estaba escondida y con el texto al revés.

- **`GET /transacciones/movimientos`**: una compra (factura) es **un solo movimiento**, con el
  total, la categoría, los chips de las etiquetas del detalle, el número de artículos y un
  texto de búsqueda que incluye **todos** los artículos (escribes «queso» y aparece la compra).
- **`GET /facturas/{id}/detalle`**: los artículos **agrupados por etiqueta** con subtotal y
  porcentaje, y cada artículo con cantidad × precio unitario. Es lo que se ve en «Ver detalle».
- **`POST /facturas/{id}/unificar`**: junta una factura confirmada línea por línea en un solo
  movimiento (crea el padre con el total, reapunta los artículos y borra los individuales).
  Idempotente y seguro: no borra una transacción que comparta otra factura.
- **Frontend**: en Transacciones, el listado agrupado con «🧾 N artículos · Ver detalle» que se
  despliega en la misma fila (acordeón, se ve bien en móvil) y el buscador entra en el detalle.
  En Facturas, la acción principal pasa a ser **«Registrar la compra»** (un movimiento + detalle,
  recomendado para el mercado) y el «separar en N movimientos» queda como opción secundaria;
  si ya confirmaste por línea, aparece «Unificar en un solo movimiento».
- Tests: **192 en verde** (antes 188): el agrupado, el detalle por etiqueta, el unificar
  idempotente y el error claro si no hay nada confirmado.

## v1.47 — IVA de las facturas y auditoría factura ↔ transacción

- **IVA**: al subir una factura se lee su bloque tributario (IVA por tarifa, ICO, descuento,
  ventas gravada/exenta/excluida) y se **concilia** contra el «Impuestos» que declara el
  documento. Se guarda el total de impuestos, el IVA (sin el ICO), el descuento y el desglose
  en JSON (migración `0029`). Además cada línea queda marcada con su tratamiento fiscal
  (`*` gravado, `**` exento, sin marca excluido) para poder decir «el X % de tu mercado no
  paga IVA». En la factura real de Cañaveral cuadra al peso: 2.148 + 75.443 + 1.022 = 78.613.
- **Auditoría factura ↔ transacción**: la ficha de la factura muestra ahora la comparación con
  la transacción asociada (✓ cuadra / ✗ no cuadra, con la diferencia). Y al asociar, si el
  monto no cuadra avisa («la factura es 1.188.248 y esa transacción es 1.888.248: no cuadra»)
  y si la factura ya tiene artículos confirmados y asocias otra del mismo valor, avisa
  «parece un duplicado del gasto». Justo el typo que te pasó a ti se habría visto al instante.
- Tests: **198 en verde** (antes 196): el bloque real que concilia, el guardado al subir, la
  marca de IVA por línea, el caso «sin dato» y los dos avisos de auditoría.

## v1.48 — Panel de Reportes con gráficas y comparación mes a mes

La pestaña de Reportes se rehizo por completo, con recharts y comparación entre meses.

- **KPIs del mes** (ingresos, gastos, balance, compras, IVA) con su variación ▲▼ vs el mes
  anterior.
- **Gráfica 1**: evolución de 12 meses (barras de ingresos/gastos + línea de balance), con
  gradientes y tooltip.
- **Gráfica 2**: gasto por categoría del mes comparado con el anterior.
- **Qué subió y qué bajó**: tabla de categorías con la variación.
- **Mercado por etiqueta**: en qué se te fue la plata (con barra y variación).
- **Artículos que más te cuestan**: top con veces compradas y precio promedio por unidad.
- **IVA**: del mes, del periodo y su peso sobre las compras.
- Todo sale de un solo `GET /reportes/panel?meses=12` (KPIs, serie, categorías, mercado e IVA).
- **Bug de fecha corregido**: `2026/9/16` se leía como `26/9/2016` porque caía en el patrón
  ambiguo `D/M/Y`. Ahora se reconoce el año de 4 cifras primero.

Tests: **199 en verde** (antes 198).

## v1.49 — Leer la foto de un recibo (parqueadero) y afinar etiquetas

- **La foto ya se leía**: `extraer_texto` hace OCR con tesseract (español) desde antes.
  Lo que fallaba era el **tratamiento**: la foto de un parqueadero producía **seis
  «artículos»** que en realidad eran la cabecera (NIT, dirección, correo, número de
  resolución) y el documento se clasificaba como **mercado**.
  - **Filtro de ruido de fotos**: se descartan correos y URLs, descripciones que son casi
    todo números, números gigantes (una resolución de 18 billones no es un precio) y
    etiquetas de documento (`No:`, `Ref.`, `CUFE`…). Además `IGNORAR` ganó las palabras de
    cabecera que salen en las fotos (`AVENIDA`, `INGRESO`, `MATRICULA`, `DURACION`,
    `OPERARIO`, `POLIZA`, `SOFTWARE`…).
  - **Tipo de documento `parqueadero`**: un recibo con `PARKING` ya no se confunde con un
    mercado (antes, «muchas líneas ⇒ mercado»).
  - **Recibo sin artículos**: `confirmar-total` ahora funciona con **cero líneas** y usa el
    monto detectado; en la ficha aparece «Registrar el gasto» con la categoría y la
    etiqueta ya propuestas (**Transporte › Parqueadero**). Validado con la foto real:
    TOTAL **4.100**, fecha **2026-09-29**, **0 artículos** inventados.
- **Etiquetas nuevas**: `Parqueadero` y `Peajes` en Transporte (migración `0030`).
- **Auditoría de las 120 líneas reales** (lo que pediste): correcta salvo **una** —
  `SALSA FRUCO*165ml CARNES` caía en **Carnes** porque la palabra CARNES le ganaba a SALSA.
  Se arregla con la marca completa y queda en **Despensa**.
- Tests: **204 en verde** (antes 199), con el texto OCR **real** de la foto como fixture
  (sin depender de tesseract en CI).

### v1.49.1 — «Transporte público» y «Uber / DiDi» no clasificaban nada

La auditoría de tus etiquetas destapó el mismo problema que tenían Lácteos y Cuidado
personal: **existían en la cuenta pero sin ninguna palabra** en el diccionario, así que un
pasaje de Transmilenio o un viaje de Uber no se etiquetaban nunca. Ahora
«Transporte público» reconoce Transmilenio, SITP, metro, buseta… y «Uber / DiDi» reconoce
Uber, DiDi, Cabify, InDrive, Beat y taxi. Con su test.

Tests: **205 en verde**.

### v1.49.2 — La foto no llegaba al OCR (bug que encontraste al subirla)

Subiste la foto del parqueadero y salió **«Monto detectado: —»** con un **400** al leer
líneas. La causa: el endpoint de subida llamaba a `extraer_texto(contenido)` **sin el
nombre ni el tipo de archivo**, y sin ellos `extraer_texto` no sabe que es una imagen: la
trataba como PDF, fallaba y devolvía texto vacío. El OCR de imágenes existía desde antes
pero **era inalcanzable desde la API**.

- Ahora la subida pasa `archivo.filename` y `archivo.content_type`.
- Si el OCR de una foto no consigue texto, el mensaje lo dice: «No pudimos leer el texto de
  la foto (OCR): prueba con más luz, el recibo recto y sin sombras».
- Tests: **207 en verde**, con uno que vigila que la subida **siempre** le pase el nombre y
  el tipo al extractor (es el bug exacto, y sin depender de tesseract).

## v1.50 — El QR de la factura (CUDE de la DIAN) y no inventar artículos

Viste que la foto del parqueadero generaba **3 artículos falsos** (`Eta $2.026`,
`SE Rango desde $85.550`, `asta $500.000`, que son el pie del recibo: «Rango desde 85550»,
«Hasta 500000»). Y propusiste algo mejor que el OCR: **el QR**.

- **Un recibo de servicio no genera artículos.** Si el documento es de tipo `parqueadero` o
  `servicios`, sus «líneas» son cabecera y pie: no se guardan. La ficha muestra 0 artículos y
  el botón «Registrar el gasto» con el total detectado.
- **Filtro reforzado**: `RANGO`, `DESDE`, `HASTA`, `VIGENCIA` al `IGNORAR`, y las
  descripciones de menos de 5 caracteres (o con menos de 4 letras) ya no son «artículos».
- **Se lee el QR** de la foto (y de la primera página del PDF) con `zxing-cpp`, **sin
  depender del OCR**: de ahí salen el **CUDE** (código único del documento en la DIAN) y la
  **URL oficial** de consulta. Migración `0031`.
- **Duplicados**: dos facturas con el mismo CUDE son el mismo documento. Al subir una
  repetida, la app avisa «ya la habías subido».
- La ficha muestra el CUDE y un enlace **«Ver en la DIAN ↗»**.
  **Límite honesto**: la descarga automática del PDF oficial **no** es posible sin sesión
  (probado: `/User/SearchDocument` devuelve el formulario de acceso). Lo que sí se puede es
  abrir el enlace con tu cuenta, descargar el PDF oficial y subirlo: ese se lee perfecto
  porque es digital y trae la tabla de artículos.
- Tests: **211 en verde** (antes 207).

## v1.51 — Dos bugs al cargar un extracto de **cuenta**

Al abrir un extracto, la página reventaba con `p.map is not a function` y el previo de
importación devolvía **500**. Eran dos bugs distintos, **ninguno** de los cambios del día:

- **Frontend**: `Extractos.tsx` hacía `api<Cuenta[]>('/cuentas')`, pero `GET /cuentas`
  devuelve el **resumen con saldos** (un objeto), no una lista. Las otras siete páginas ya
  hacían `r.cuentas`; Extractos no, así que `cuentas` quedaba como objeto y `cuentas.map`
  tumbaba la página al pintar el selector «Sale de». Arreglado leyendo `.cuentas`.
- **Backend**: `ImportarLineaOut.movimiento_id` exigía un UUID, pero los **intereses y
  comisiones que declara el corte** no son movimientos: se sintetizan como líneas a importar
  con `movimiento_id` nulo. En un extracto de **tarjeta** no se notaba (no declara
  intereses); en uno de **cuenta** el previo devolvía 500. Ahora es opcional, con test.
- Tests: **212 en verde** (antes 211).

## v1.52 — La conciliación del CMR (Falabella) ya cuadra

Era la tarea 15 del backlog, aparcada desde el principio: el extracto del CMR se leía pero
**la conciliación no cuadraba**. Tres causas, todas de diseño del PDF de ese banco:

- **La columna «Cuota a pagar este mes» no se detectaba.** El encabezado viene partido en
  tres renglones (`Cuota a` / `pagar` / `este mes`) y el nombre del grupo se armaba **de
  abajo hacia arriba**, así que quedaba `ESTEMESPAGARCUOTAA` y no casaba con nada. Ahora se
  prueba el orden de lectura correcto y la columna se detecta (x≈605).
- **La fila del pago no cae en la columna de valor.** El CMR dibuja su `-$612.126,00` en la
  x de la cuota. La fila quedaba **abierta** (sin valor) y se tragaba el importe del renglón
  siguiente: el pago aparecía con `$86.090,03` y la compra de PAYPAL se quedaba sin su peso.
  Ahora, cuando una fila no tiene valor pero sí cuota y no trae «N de M», ese importe es su
  valor (y el pago se cierra en su renglón).
- **Algunas celdas llegan con los dígitos separados y el extractor pierde un cero**
  (`$8.000,00` llega como `$ 8.0 0 ,0 0` → 800). Se detecta por el espaciado y se corrige con
  la **aritmética del propio extracto**: el capital por cuota que queda (`pendiente / (M-N)`)
  o, en una compra de una sola cuota, el valor de la compra. Con eso las 30 cuotas coinciden
  una a una con el PDF.
- **«Consumos del mes facturados» es el CAPITAL** facturado, no el valor de las compras: el
  control ahora suma la cuota del mes de **todas** las compras pendientes (no solo las del
  periodo). Y la deuda se calcula con los «consumos del periodo» y el seguro de vida, que el
  banco declara aparte.

Resultado con el archivo real: **capital facturado 489.088,85 = declarado**, **pagos
612.126,00 = declarado**, **pago total 2.771.831,16 = declarado** y **`conciliacion_ok`**.
De paso, el parser por coordenadas estrena tests (fragmentos sintéticos): era lo único sin
cobertura, y por eso estos bugs pasaron.

Tests: **216 en verde** (antes 212).

### v1.52.1 — El «cupo utilizado» ahora se comprueba de verdad

El control salía en `--` porque el corte declara «Has utilizado: $2.771.831,16» y el parser
no lo leía: solo se calculaba `cupo_total − cupo_disponible`. Ahora ese valor declarado se
lee (y se **comprueba** contra el calculado) → `5.660.000,00 − 2.888.168,84 = 2.771.831,16`,
que es exactamente lo que dice el corte. Con el cuidado de no confundirlo con «Cupo utilizado
**de avances**», que es otra cosa: la palabra que descalifica una etiqueta puede ir antes
(`Capital facturado consumos…`) o después (`Cupo utilizado de avances`), así que ahora se
miran las dos.

Tests: **217 en verde**.

> Nota: el valor declarado se guarda en la columna `extractos.cupo_utilizado`
> (migración `0032`), no solo en el dataclass del parser: el análisis lee del **modelo**,
> y sin la columna el endpoint devolvía `AttributeError` (lo cazó el test del Excel de
> Amex, que no declara cupo).

## v1.53 — Subir una factura electrónica con contraseña (el NIT del emisor)

Las facturas electrónicas llegan en **PDF protegido**, casi siempre con el **NIT del emisor**
como contraseña. La subida de facturas no tenía dónde escribirla, así que el PDF no se podía
abrir y la app decía «no tiene texto extraído» — que además confundía dos cosas distintas.

- **Backend**: `extraer_texto` acepta la contraseña y hace `decrypt`; si el PDF está protegido
  y la clave falta o no sirve, **lo dice** («El PDF está protegido y la contraseña no es
  correcta», igual que ya hacían los extractos) en vez de devolver un texto vacío. El OCR de
  un PDF escaneado también usa la contraseña.
- **Pantalla de Facturas**: campo de contraseña + botón «Subir factura» (antes se subía al
  elegir el archivo, sin oportunidad de escribirla). Si falla, se conservan el archivo y la
  contraseña para corregirla; el campo es `type="password"` con `autocomplete="off"`.
- Tests: **221 en verde** (antes 217), con un PDF protegido de verdad creado en el test.

## v1.54 — La marca: la K Ascendente ya está en la app

Konta no tenía **ningún** icono: ni favicon, ni manifiesto, ni marca en la interfaz (el
navegador mostraba el icono genérico). Se integra la propuesta elegida, **«K Ascendente»**:
la K blanca con el brazo de arriba en esmeralda —el trazo que sube— sobre el degradado
índigo→violeta de la app.

- **`favicon.svg`** (vectorial, nítido a cualquier tamaño) + **`favicon.ico`** con 16/32/48
  para los navegadores que no leen SVG.
- **`apple-touch-icon`** (180) para el icono al añadir la app a la pantalla de inicio.
- **PWA**: `icon-192`, `icon-512` y una versión **maskable** a sangre con la K dentro del 80%
  seguro (Android recorta el icono con su propia forma; sin ese margen se comería el trazo).
- **`manifest.webmanifest`** con nombre, colores y `display: standalone`, y el
  **`theme-color`** `#4f46e5` en el `index.html` (la barra del navegador en móvil).
- **En la interfaz**: la marca (la K sin el cuadro, en índigo con el brazo esmeralda) en la
  **cabecera** y en el **login**. Va como SVG en línea, así que hereda el tamaño y no cuesta
  una petición.

Los PNG se generan desde el mismo dibujo (a 4096 y reducidos con LANCZOS), así que el
antialiasing es idéntico en todos: el script está en `.tools/tmp/iconos/exportar_marca.py`.

## v1.55 — Releer una factura ya registrada ya no duplica sus líneas

Apareció con una factura del mercado: **240 líneas y la suma al doble del total** (2.376.496
en vez de 1.188.248), con cada artículo repetido y una copia marcada «confirmada» (la que
estaba en el movimiento) y otra «diccionario» (la nueva).

No era la pantalla: en la base había dos lecturas **de verdad**, separadas por cinco horas.
El endpoint de «Leer líneas» dice ser idempotente y borra las líneas anteriores… pero solo
las que **no** tienen movimiento. A las 06:52 se leyeron 120 líneas y se registró la compra
(las 120 quedaron dentro del movimiento); a las 12:07 se volvió a leer: no había nada que
borrar, así que se añadieron otras 120.

- **Arreglo**: al releer, los artículos que ya están dentro de un movimiento se **omiten** en
  vez de insertarse otra vez. Se emparejan uno a uno (dos «BOLSA CANAVERAL» iguales son dos
  líneas) por `(orden, valor)` y, si la descripción se corrigió a mano, por
  `(descripción, valor)`. Lo que aparezca **nuevo** sí se añade, pendiente de confirmar.
- **Aviso**: la respuesta y la pantalla dicen cuántos se omitieron («N de M artículos ya
  estaban dentro de un movimiento: no se duplicaron»).
- **Antes de releer**, si la factura ya está registrada, la pantalla **pregunta**.
- Tests: **224 en verde** (3 nuevos: releer sin duplicar, releer con un artículo nuevo, y
  releer sin registrar, que sigue reemplazando).

## v1.56 — Pedidos de fuera (Amazon) y el IVA que no existe

Salió de una pregunta: *«esta transacción que hice con tarjeta de crédito, ¿cómo ingreso los
datos del pago para que valide el IVA?»*. La respuesta es que **en esa compra no hay IVA que
validar** (`Impuestos: COP 0`), pero al comprobar cómo se leía el pedido aparecieron **tres
fallos** en el parser:

- **El «cambio» se comía una comisión.** `CAMBIO` estaba en la lista de palabras ignoradas y
  descartaba cualquier línea que la contuviera, así que *«Cuota de garantía del tipo de
  cambio: 1.971,70»* —una comisión que sí se pagó— desaparecía. Ahora `CAMBIO` solo descarta
  la línea cuando **es la etiqueta** (el cambio que devuelven en un recibo), y las líneas de
  tasa (`1 USD = 3370.42 COP`) se saltan aparte.
- **El signo negativo no se capturaba.** `-COP 38.456,49` (envío gratis de Prime) se leía como
  **+38.456,49**: el envío se contaba como un cobro y el detalle sumaba 164.542 en vez de
  89.602,62. Ahora el menos que va antes del símbolo se detecta y el descuento entra en
  negativo. (Un descuento **no** genera un movimiento por sí solo: al confirmar línea por
  línea se omite, para no crear un gasto en negativo.)
- **Se perdían los centavos.** El patrón de dinero paraba en el grupo de miles, así que
  `87,630.92` se leía como 87.630. Amazon imprime los pesos en formato gringo y ahí se
  perdían los centavos de todas las líneas.

Con los tres, el detalle del pedido cuadra **al centavo** con su total (89.602,62) y no hay
que tocar nada a mano. Y el IVA: si la factura trae `Impuestos: 0`, la app **no inventa** un
IVA (el impuesto de una importación lo cobra la DIAN en la aduana, no el vendedor). La comisión
del cambio va como parte del costo, con su etiqueta, no como impuesto.

Tests: **229 en verde** (5 nuevos).

## v1.57 — Las fotos grandes ya suben (el 413 invisible)

El síntoma: se elegía una foto, se pulsaba «Subir factura» y **no aparecía nada** — ni la
factura, ni el botón «Leer líneas», ni un error que explicara nada.

La causa: **nginx corta las subidas en 1 MB por defecto** y una foto de móvil pesa más. Las
fotos de WhatsApp sí entraban porque WhatsApp las comprime mucho; una captura o una foto
normal no. Y como nginx responde con una **página HTML**, el frontend no podía leer el
`detail` y el mensaje se quedaba en «HTTP 413», que no dice qué hacer.

- **nginx**: `client_max_body_size 15m`.
- **Backend**: el mismo límite en `FINANZAS_TAMANO_MAXIMO_ARCHIVO_MB` (15 por defecto) con un
  aviso claro: *«El archivo pesa más de 15 MB. Bájale la calidad a la foto o recórtala»*.
  Vale para facturas **y** extractos.
- **Frontend**: un 413 se traduce a ese mismo mensaje en vez de «HTTP 413».

Los dos límites tienen que ir juntos y están comentados en los dos sitios para que no se
separen. Tests: **231 en verde** (2 nuevos).

## v1.58 — Leer escaneados grandes (el 504 por tiempo)

Con el límite de tamaño ya en 15 MB quedaba el otro techo, que no se ve: **el tiempo**. Un
PDF escaneado se lee con OCR página a página y el proxy corta a los **60 s**, así que un
escaneado de 12 páginas y 2,6 MB devolvía **504 Gateway Time-out** (medido).

- **Rasterizado a 150 ppp** en vez de 200: un documento de texto se lee igual y va bastante
  más rápido.
- **Tope de 25 páginas** para el OCR. El texto **digital** (una factura electrónica o un
  extracto descargado del banco, que es el caso normal) no pasa por el OCR y **no tiene
  tope**.
- **nginx**: `proxy_read_timeout`/`send_timeout` a 300 s, para que el margen no sea el que
  decide.
- **Pantalla**: un 504 dice qué pasa («tardó demasiado… prueba con las páginas que
  necesitas») en vez de un número.

Con esto entran archivos de **hasta 15 MB**, muy por encima de los 5 MB que pediste.

## v1.59 — El OCR era 150 veces más lento de lo que debía (OpenMP)

Lo que parecía un problema de pesos y tiempos era uno solo, y estaba escondido: **Tesseract usa
OpenMP y, sin límite, lanza más hilos de los que el servidor puede atender**. Se pelean entre
ellos y el OCR se arrastra. Medido en el contenedor, la misma página:

| | tiempo |
|---|---|
| sin límite de hilos | **42,20 s** |
| `OMP_THREAD_LIMIT=1` | **0,28 s** |

Eso explicaba los tres síntomas que veníamos persiguiendo: el **504** al subir un escaneado de
12 páginas, la CPU del contenedor al 190 % durante minutos y los **236 s por página**. El
recibo real de parqueadero pasaba de 67 s a menos de uno.

- `OMP_THREAD_LIMIT=1` antes de llamar a Tesseract (con `setdefault`, para poder subirlo por
  entorno si algún día conviene). Va donde se usa el OCR: `app/facturas.py`.
- Se mantienen el OCR a 150 ppp y el tope de 25 páginas: con el arreglo son unos segundos, y
  el texto **digital** sigue sin pasar por el OCR ni tener tope.

Con esto, los archivos de hasta 15 MB —y muy por encima de los 5 MB que pediste— se leen sin
esperas. Tests: **231 en verde**.

### v1.60.1 — Subir una factura vuelve a ser un solo paso

Al añadir el campo de contraseña, la subida pasó a necesitar un botón («Subir factura»): quien
elegía el archivo y no lo pulsaba no veía la factura ni, por tanto, el botón «Leer líneas».
Vuelve a subirse **al elegir el archivo**. La contraseña sigue teniendo su camino: si el PDF
está protegido, el aviso lo dice, el archivo se queda elegido y se reintenta con el botón
(que ahora se llama «Volver a subir»).

También: la tarjeta de la factura usa `flex-wrap` y el nombre `break-words`, para que un
nombre largo no empuje los botones fuera de la pantalla; y al subir se dice **siempre** qué
pasó y el paso siguiente.

### v1.60.2 — La auditoría factura ↔ movimiento, con el mismo margen que los extractos

El monto de una factura muchas veces sale del **OCR** y redondea, pero la comparación con su
transacción era **exacta**: un céntimo de diferencia salía como «✗ No cuadra» y parecía un
error de datos. Los extractos ya tenían su margen; ahora la factura también (**1 peso**), y si
la diferencia es de redondeo la ficha lo dice en vez de alarmar.

## v1.61 — «Registrar el gasto» devolvía 422 (el select vacío)

En un recibo **sin artículos** (una captura que el OCR no parte), pulsar «Registrar el gasto»
devolvía **422 Unprocessable Entity** y el gasto no se registraba.

La causa, en la pantalla: el botón mandaba `categoria_id: ""` y `etiqueta_id: ""`. En
JavaScript `"" ?? null` **no** salta (el `??` solo actúa con `null`/`undefined`), así que la
cadena vacía del select llegaba al backend y `""` no es un UUID.

- **Pantalla**: `||` en vez de `??` en ese payload (`"" || "" || null` → `null`).
- **Backend**: los campos de UUID de `ConfirmarLineasIn` aceptan `""` como «sin valor». Tolerar
  el vacío de un formulario no es tolerar cualquier cosa: un texto que no sea un UUID sigue
  dando 422.
- De paso, el campo de contraseña usa `autocomplete="new-password"`, que quita el aviso del
  navegador («Password field is not contained in a form»).

Tests: **233 en verde** (2 nuevos).

## v1.62 — Separar los gastos por lugar (casa / apartamento)

La app guarda `Categoría › Etiqueta › Subetiqueta` y los reportes agrupan por esa ruta, pero
los selectores de etiqueta **solo ofrecían dos niveles**: una subetiqueta de tercero (por
ejemplo `Suscripciones › Streaming › Netflix`) no se podía elegir. Ahora bajan todo el árbol.

Para distinguir **dónde** es el gasto, la forma que mejor funciona con los reportes es:

- **Categoría = el lugar** (`Casa`, `Apartamento Yumbo`): el gráfico por categoría te da el
  total de cada sitio de un vistazo.
- **Etiqueta = el servicio** (Arriendo, Energía, Acueducto, Gas, Internet): el desglose por
  etiqueta te dice en qué se va dentro de cada lugar.
- **Subetiqueta (opcional)** = el proveedor o el detalle (`Internet › Claro`).

Poner el lugar en la etiqueta y el servicio en la descripción también «funciona», pero
entonces los reportes no te dan el total por sitio sin sumar a mano.

## v1.63 — El saldo actual ya no cuenta el futuro

Salió de un «mi saldo está al doble»: el **saldo actual** de una cuenta sumaba los movimientos
**sin mirar la fecha**, así que un sueldo recurrente fechado un mes por delante se contaba como
si ya estuviera cobrado. Con un saldo inicial de 11.837.735 y un ingreso de 11.783.952 en
octubre, la cuenta mostraba **23.621.687**.

Un saldo «actual» es el de **hoy**: ahora solo cuentan los movimientos con fecha de hoy o
anterior, en las cuentas, en las transferencias, en los movimientos sin cuenta y en el saldo
de una cuenta concreta. Los del futuro siguen ahí (y salen en su mes en la vista mensual),
pero no inflan lo que tienes ahora.

Tests: **235 en verde** (2 nuevos).

## v1.64 — Una compra con tarjeta de crédito no es «sin cuenta»

El Resumen avisaba de «2 movimiento(s) sin cuenta asignada por 93.702,62» y restaba ese dinero
del saldo total. Uno de los dos era una compra con **tarjeta de crédito** (89.602,62), y eso
está mal por partida doble: es **deuda de la tarjeta** (el dinero no sale de ninguna cuenta
hasta que pagas la tarjeta, el 5 de octubre) y, al restarla ahora, se restaba **dos veces** (al
comprar y al pagar). Además pedía asignarle una cuenta, que no es lo que corresponde.

Ahora las compras con tarjeta de crédito quedan fuera de «sin cuenta» (del neto, del conteo y
de la alerta). Las de **débito** y el efectivo sí cuentan: ese dinero sí sale.

Tests: **236 en verde** (1 nuevo).

## v1.65 — Que tome cualquier factura: PDF de dos columnas y montos con sentido

Con un **comprobante de pago de EMCALI** (PDF digital de dos columnas) la app hacía tres
cosas mal:

| Lo que pasaba | Lo que debía |
|---|---|
| Monto: **260.930.020.535** ✗ (del consecutivo `TR260930020535rBgAnc`) | **844.041** (el «Valor del Pago») |
| Tipo: «mercado», con 2 artículos inventados (una fecha y `**** 0571`) | «servicios», sin artículos |
| Texto: 405 caracteres mezclados | 740 ✂, con cada etiqueta junto a su valor |

- **Se extrae el texto en modo `layout`** (como ya hacían los extractos): respeta las columnas,
  así que la etiqueta y su valor quedan en la misma línea. Es la mejora de fondo: sirve para
  cualquier factura o comprobante de dos columnas, no solo para esta.
- **El monto ya no es «el número más grande»**: ahora se buscan las etiquetas de total
  (`Total`, `Valor del Pago`, `Valor Pago`, `Valor a pagar`…) y, si no hay, se prefiere lo que
  está escrito **como dinero** (con `$` o con centavos) descartando lo que es un número de
  **documento**: lo que va pegado a letras, lo que lleva dígito de verificación (`890399003-4`)
  y lo que está junto a `Nit`, `Referencia`, `Consecutivo`, `CUS`, `Comprobante`, `IP`…
- **Se reconoce el comprobante de pago de un servicio** (`EMCALI`, `Pago PSE`,
  `Transacción Aprobada`, `Consecutivo Comercio`…) → se guarda **sin artículos**, listo para
  «Registrar el gasto» con el total.
- **`**** 0571`** (cuenta enmascarada) ya no se toma por un artículo de 571.

Tests: **242 en verde** (6 nuevos).

### v1.65.1 — El OCR lee una sola columna (confirmaciones de pago)

Con la **confirmación de pago de Gases de Occidente** (una imagen), el OCR leía las **dos
columnas por separado**: primero todas las etiquetas y luego todos los valores, así que se
perdía qué iba con qué. Medido con la imagen real:

| | antes (automático) | ahora (`--psm 4`) |
|---|---|---|
| Líneas del OCR | 24 sueltas | 14, cada etiqueta con su valor |
| «Monto: $46.477» | no existía como línea | en su sitio ✅ |

`--psm 4` dice «una sola columna de texto». En la **foto del recibo de parqueadero** da
exactamente lo mismo que antes (sin regresión). Además:

- **«Monto»** es una etiqueta de total reconocida (antes solo `Total`, `Valor del Pago`…).
- Las **confirmaciones de pago** (`¡Pago realizado con éxito!`, `Detalles del pago`,
  `Gases de Occidente`…) se reconocen como **servicio** → se guardan sin artículos, listas
  para «Registrar el gasto» con el total.

Tests: **245 en verde** (3 nuevos).

## v1.66 — El paracaídas del lector: corregir el texto y volver a leer

No se puede pretender que el lector acierte con **cualquier** formato que imprima cada banco
o establecimiento. Lo que sí se puede es que un mal lectura **nunca deje al usuario atascado**.
Esta es la primera pieza de ese plan.

- **«Corregir el texto y volver a leer»** en cada factura: se abre el texto que leyó Konta, se
  arregla y se vuelve a leer. El backend ya aceptaba un texto, pero **no lo guardaba** (la
  corrección se perdía y la factura seguía con el texto malo): ahora se guarda como el texto
  de la factura y se **re-detectan el monto y la fecha** del texto corregido.
- Lo que ya estaba confirmado no se toca (el re-parseo sigue siendo idempotente).

Tests: **246 en verde** (1 nuevo).

### v1.66.1 — Corregir el monto y la fecha que detectó el lector

La otra mitad del paracaídas. Puede que el texto esté bien y el **monto** mal (el lector tomó
un NIT, un consecutivo, o no encontró nada): hasta ahora la factura se quedaba mintiendo y la
auditoría marcaba un descuadre que no existía.

- **`PATCH /facturas/{id}`** con `monto_detectado` y/o `fecha_detectada`. Solo se aplica lo que
  venga en la petición: se puede corregir uno de los dos, o **borrarlo** con `null` (mejor sin
  monto que con uno inventado).
- **En la factura**: «✏️ Corregir» junto al monto detectado, con sus dos campos.
- Y lo importante: la **auditoría** y «Registrar el gasto» pasan a usar el monto corregido.

Tests: **250 en verde** (4 nuevos).

### v1.66.2 — Añadir artículos a mano y reordenarlos

Tercera pata del «no me quedo atascado»: ya se podía corregir y borrar una línea, pero **no
añadir** la que el lector se saltó — con el detalle mintiendo (una suma que no daba el total).

- **`POST /facturas/{id}/lineas/agregar`**: añade un artículo con descripción, valor, cantidad
  y etiqueta. Sin etiqueta, la sugiere el clasificador (como a cualquier línea).
- **`PUT /facturas/{id}/lineas/orden`**: guarda el orden nuevo de las líneas.
- **En la factura**: «➕ Añadir artículo a mano» (con su formulario) y flechas **▲▼** en cada
  renglón para subirlo o bajarlo.
- Y un detalle que hacía falta para que esto sirviera: **un re-leer ya no borra lo que pusiste a
  mano**. Las líneas manuales se conservan (y no se duplican).

Tests: **255 en verde** (5 nuevos).

### v1.66.3 — Si el monto no es de fiar, la app lo dice

Cierra el Nivel 1 del plan. El caso que lo motivó: una confirmación de pago subida con una
versión anterior del lector quedó con un monto de **695.417.658** (el CUS) y la lista lo
mostraba tan tranquila. La app no inventa números, pero tampoco puede callarse cuando algo no
cuadra.

Ahora cada factura trae un **`aviso_monto`** con el motivo, y se ve **ya en la lista** (sin
abrir el detalle) al lado del monto, con el botón de corregir ahí mismo:

- **Sale de un número de documento**: si todas las apariciones de ese número en el texto están
  pegadas a un NIT, una referencia, un comprobante… (típico en facturas viejas).
- **Es inverosímil**: 100 millones o más para un recibo de pago.
- **No cuadra con los artículos**: el monto detectado contra la suma de las líneas, con margen
  del 25 % para no chillar por IVA o descuentos (una factura con IVA **no** dispara el aviso).
- **No se pudo leer**: «escríbelo tú» en vez de dejar la factura en blanco sin explicación.

De paso, un fallo que salió al escribir esto: la comprobación de «número pegado a letras»
miraba el carácter anterior a los **espacios**, así que `TOTAL 11.800` contaba como pegado y el
monto se descartaba. Ahora mira el carácter justo anterior al número.

Tests: **260 en verde** (5 nuevos).

### v1.66.4 — Un monto que no cabe se explica (antes era un 500)

Persiguiendo el aviso del monto salió un fallo de fondo: **ningún** campo de dinero validaba el
tamaño. Las columnas son `NUMERIC(14,2)` (hasta 999.999.999.999,99) y un número más grande no
cabe — la petición reventaba con un **500** en vez de decir qué pasaba. Y pasa con facilidad:
una referencia o un CUS tienen más dígitos que un precio.

Ahora se valida antes de tocar la base, con un mensaje que orienta: *«El monto no puede pasar
de 999.999.999.999,99. Revisa que no sea un número de documento (NIT, referencia,
comprobante)»*. Aplica a corregir el monto de una factura, a registrar un gasto, a editarlo y
a las líneas de una factura.

Tests: **261 en verde** (1 nuevo).

### v1.67 — Modo revisión: monto, fecha y artículos en una pasada (cierra el Nivel 1)

Después de leer, la factura muestra un panel **«Revisa antes de registrar»** con los tres
puntos que deciden si el gasto queda bien, cada uno con su estado y su **Corregir** al lado:

| | |
|---|---|
| **Monto** | ✅ o ⚠️ con el motivo (y el botón para corregirlo) |
| **Fecha** | ✅ o ⚠️ — y aquí está lo nuevo |
| **Artículos** | «3 artículos · suman 15.000» o «sin artículos: se registra como un solo gasto» |

La corrección deja de ser un rescate cuando ya algo salió mal y pasa a ser parte del flujo.

**Lo nuevo en la fecha**: la fecha decide en **qué mes** cae el gasto, así que una fecha que
falta o que está en el futuro descoloca los reportes sin que se note. Ahora también trae su
`aviso_fecha` (con un día de gracia, porque un recibo de madrugada puede quedar fechado
«mañana» por la zona horaria del emisor) y, si parece una factura de mercado y no se detectó
ningún artículo, el panel lo advierte en vez de registrarla vacía.

Tests: **266 en verde** (4 nuevos).

### v1.68 — La segunda opinión del OCR (empieza el Nivel 2)

Un solo modo del OCR no acierta con todos los documentos: el de **una columna** (`--psm 4`)
mantiene cada etiqueta con su valor —lo que hace falta en una confirmación de pago— pero el
**automático** separa mejor las columnas de una tabla. Ahora, cuando la primera lectura **no
trae un monto de fiar**, se pide una segunda opinión y se conserva la que más confianza
merece. Si la primera ya está bien, no se lee dos veces (nada de pagar el doble por gusto).

**Cómo se puntúa una lectura**: encontrar el monto son 4 puntos, y que además sea de fiar
(sin aviso de número de documento ni de cifra inverosímil) otros 4; sacar artículos, 2; y
reconocer el tipo de documento, 1. Por debajo de 8 se reintenta.

**Medido con los documentos reales** (la confirmación de Gases de Occidente, que es una captura
de dos columnas):

| Modo | Puntaje | Monto | Artículos | ¿Aviso? |
|---|---|---|---|---|
| `--psm 4` (1 columna) | **11** | **46.477** ✅ | 1 | no |
| `auto` (separa columnas) | 5 | 800.167.643 ✗ (el NIT) | 0 | sí |

Y en una tabla de mercado (imagen sintética, columnas de artículo/cantidad/valor) **empatan**
(11 y 11: monto 15.000 y 3 artículos), así que el reintento no rompe nada donde ya iba bien.
Dicho con honestidad: en las muestras medidas **gana la primera lectura**; el reintento es una
red que solo se paga cuando la primera falla, que es justo el caso en que hoy tocaría
arreglarlo a mano.

Tests: **271 en verde** (5 nuevos).

## v1.69 — Plantilla por emisor: la app se aprende el formato de cada casa

**La tarea más importante del plan.** No se puede ir a cada banco o establecimiento a pedirle un
formato, pero sí se puede aprender: cuando corriges el monto o la fecha de una factura, Konta
guarda **en qué etiqueta venían** —«en los documentos de este emisor el total está donde dice
MONTO»— y la próxima factura del mismo emisor sale bien **a la primera**.

- **Se identifica al emisor**: por su **NIT** (`nit:9001234567`, lo único que escribe siempre
  igual) o, si no lo trae, por su nombre. Queda guardado en la factura.
- **Lo aprendido manda**: al subir, si hay plantilla para ese emisor se busca el total y la fecha
  en la etiqueta aprendida antes de adivinar (y el tipo de documento aprendido decide si se
  registra como un solo gasto o por artículos).
- **El usuario puede verlo y borrarlo** en *«lo que el OCR ha aprendido»* → **Plantillas por
  emisor**, con cuántas veces ha servido cada una. Al borrarla, esa casa se vuelve a leer
  adivinando (que es lo honesto).

Medido en la prueba de producción: un documento donde el lector se equivocaba (tomaba 120.000 en
vez de 50.000) → se corrige una vez → la factura siguiente del mismo emisor se lee en **60.000**
sola, sin avisos, y la plantilla cuenta su primer uso.

De paso, dos arreglos que salieron al construirlo:

- El aviso de «monto que sale de un número de documento» miraba 26 caracteres hacia atrás **sin
  respetar el salto de línea**, así que el NIT del renglón anterior descartaba un monto bueno.
  Ahora la etiqueta vale para **su** línea.
- `GET /facturas/plantillas-lector` iba declarado después de `/{id}`, que se lo comía.

Tests: **276 en verde** (5 nuevos).

### v1.70 — Los renglones que no son artículos (cierra el Nivel 2)

Un recibo trae «Nit: 900123456», «Cajero: 12», «Cambio: 0» o el IVA entre los renglones, y el
lector los podía tomar por productos: el detalle quedaba con basura y la suma no cuadraba.

- **Los comunes ya se descartan siempre**: NIT, cédula, cajero, terminal, POS, autorización,
  resolución, «Factura No», subtotal, IVA, impuesto, base gravable, descuento, propina,
  redondeo, efectivo, total, monto, fecha, hora, cliente, vendedor, cambio, vueltas. Se
  comparan como **prefijo** de la línea, así que la lista solo lleva palabras que no pueden
  empezar el nombre de un producto.
- **Y aprende los demás**: cuando borras un renglón, Konta guarda su patrón (normalizado y sin
  números: «PUNTOS GANADOS 150» → `PUNTOS GANADOS`). **A la segunda vez** que lo borras, deja de
  proponerlo — una vez podría ser un error, dos es un patrón — y lo dice en el aviso de la
  factura.
- **Puedes verlo y deshacerlo** en *«lo que el OCR ha aprendido»* → **Renglones que no son
  artículos**, con «Volver a tenerlo en cuenta» por si borraste algo que sí era un artículo.

Aviso de alcance: de los tres criterios de esta tarea, el **total** y el **tipo de documento**
por emisor ya quedaron aprendidos en la tarea anterior (en `plantillas_lector`, que es más
preciso que `reglas_ocr` porque distingue por emisor). Lo que faltaba de verdad eran los
renglones, y es lo que trae esta versión.

Tests: **280 en verde** (4 nuevos).

## v1.71 — El buzón de casos: «esta factura la leyó mal» (empieza el Nivel 3)

No se puede ir a cada establecimiento a pedirle un formato, pero sí se puede **acumular lo que
falla**. Hasta ahora eso se hacía a mano —tú mandabas la captura, yo lo arreglaba y lo dejaba
como test—; ahora es un botón.

En cada factura: **«🐞 Esta factura la leyó mal»** → un motivo (opcional) y, si quieres, el
documento adjunto. El caso guarda:

- el **texto** leído,
- lo que **dice el lector** sobre ese texto (aunque ya lo hayas corregido),
- con **qué te quedaste** al final,
- el emisor y el tipo de documento, y
- el archivo original **solo si lo adjuntas** (las facturas no guardan el archivo: solo el
  texto; el documento se sube a propósito en el caso).

Y lo importante: cada caso tiene **«Ver el test»**, que devuelve la maqueta lista para pegar en
`tests/` —el texto tal cual y lo que se espera de él—. Es el puente entre «esto se leyó mal» y
«esto no se vuelve a romper»: exactamente lo que hoy hago a mano con tus documentos. En *«lo
que el OCR ha aprendido»* → **Facturas que se leyeron mal** se ve el buzón, se marca un caso
como resuelto y se borra.

Tests: **285 en verde** (5 nuevos).

## v1.72 — Panel de calidad del lector (cierra el Nivel 3 y el plan)

Con todo lo anterior ya había datos para saber **dónde** falla el lector; lo que faltaba era
mirarlos juntos. Ahora se guardan dos cosas por factura —si hubo que **corregirla** (al cambiar
el monto, la fecha, el texto o cualquier línea) y si salió bien **gracias a una plantilla
aprendida**— y el panel las cruza por emisor:

- **% sin corrección** sobre el total, con su barra.
- **Por emisor**: documentos, sin corrección, corregidas, leídas con plantilla y casos
  reportados.
- Y los **casos abiertos** del buzón.

Está en *«lo que el OCR ha aprendido»*, arriba del todo, porque es el resumen que enmarca lo
demás: si una casa falla siempre, ahí está el trabajo; si el 90 % entra solo, el lector está
haciendo su trabajo.

Con esto se cierran los tres niveles del plan: **Nivel 1** (arreglarlo tú: texto, monto, fecha,
artículos, avisos y modo revisión), **Nivel 2** (que aprenda: doble lectura, plantilla por
emisor y renglones que no son artículos) y **Nivel 3** (mejorarlo: buzón de casos con su test y
este panel).

Tests: **290 en verde** (5 nuevos).

## v1.73 — Lecturas de factura con IA, con cuota por plan

La IA entra como **segunda opinión** para los documentos que el OCR local no puede (manuscritos,
fotos torcidas, formatos raros). No sustituye al lector de siempre: se pide a propósito, cuesta
dinero y va limitada por el plan.

**Lo que se construyó**

- **Catálogo de planes** (`planes`, migración 0037): Básico $6.000/mes con 10 lecturas,
  Personal $12.000 con 30 y Pro $29.000 con 100. Son **datos**, no código: los límites se
  cambian sin tocar la aplicación.
- **Medidor por mes** (`consumos_ia`): lecturas, consultas y —lo que de verdad importa— los
  **tokens y el coste real en dólares** que facturó el proveedor. Sin eso no se sabe el margen.
- **Saldo comprado aparte** (`usuarios.lecturas_extra`): cuando se agota lo incluido, se gasta
  este saldo. Es el «y a partir de ahí leer más».
- **API de lectura con IA**: `POST /ia/leer` (una imagen o un PDF) devuelve la factura normal,
  con su texto, su monto y sus avisos, lista para revisar y registrar con las herramientas de
  siempre. Más `GET /ia/planes` y `GET /ia/cuota`.
- **Tres reglas que protegen el dinero**: el cupo se comprueba **antes** de llamar al proveedor
  (si no hay, no se gasta un token), se descuenta **solo si la lectura sale bien** (un fallo del
  proveedor devuelve 502 y no cobra) y sin clave la función está **apagada**, no rota (503).
- El monto que devuelve el modelo **pasa por las mismas reglas de la app**: si no cuadra, sale
  con su aviso y el usuario lo corrige.

**El coste, con los precios verificados del proveedor** (1.024 tokens por imagen como máximo,
imagen ~1.000 + instrucciones ~300, salida ~400):

| | por lectura |
|---|---|
| Hora valle | ≈ $0,00044 (≈ **1,8 COP**) |
| Hora pico | ≈ $0,00087 (≈ **3,5 COP**) |

O sea: las 10 lecturas del plan Básico cuestan del orden de **20–35 pesos al mes**. El coste de
los tokens **no** es lo que decide el precio del plan; la cuota está para evitar abusos y para
segmentar planes. El único sitio donde el gasto puede crecer de verdad es el asistente de chat,
que se medirá igual.

Tests: **298 en verde** (8 nuevos).

### v1.73.1 — Validación de la lectura con IA (con clave real)

Siete documentos por los **dos** lectores: 4 reales (confirmación de pago, foto de un recibo,
PDF de dos columnas y una tabla de mercado) y **3 degradados a propósito** (desenfocado,
reducido a un tercio y girado 7°).

| Documento | Lector local | IA |
|---|---|---|
| tabla limpia | 15.000 ✅ | 15.000 ✅ |
| **desenfocado** | **18** ✗ | **15.000** ✅ |
| **reducido a 1/3** | **15** ✗ | **15.000** ✅ |
| girado 7° | 15.000 ✅ | 15.000 ✅ |
| confirmación de pago (2 columnas) | 46.477 ✅ | 46.477 ✅ |
| foto de un recibo | 4.100 ✅ | 4.100 ✅ |
| PDF de dos columnas | 844.041 ✅ | 844.041 ✅ |

**La IA acierta donde el lector local se rinde** (desenfoque y poca resolución), y empata en el
resto. Es exactamente el hueco que justifica la función: no reemplaza al lector, lo tapa.

**Coste medido** (7 lecturas): 4.256 tokens de entrada y 14.026 de salida → 0,018108 USD
≈ **72 COP**, o **≈ 10 COP por lectura** con los precios configurados (tarifa pico; en valle es
la mitad). El gasto lo manda la **salida** (≈2.000 tokens por documento: el modelo transcribe
todo el texto, que es justo lo que la app aprovecha). Tiempo: de 3,9 a 21 s según el documento.

Con eso, las 10 lecturas del plan Básico cuestan del orden de **100 pesos al mes**: el margen
sigue siendo del 98 % y confirma que el precio del plan se pone **por valor**, no por tokens.

### v1.73.2 — «Leer con IA» en la pantalla, con el cupo a la vista

La lectura con IA ya se puede usar desde la app: en la zona de subida hay un interruptor
**«🤖 Leer con IA»** con las lecturas que quedan este mes y, al lado, **Ver planes** con el
catálogo y cuál es el tuyo.

- **Es a propósito**: el interruptor se enciende cuando quieres, porque cuesta una lectura. No
  se duplica nada: con el interruptor puesto, el mismo archivo va por el camino de la IA en vez
  del lector normal.
- **Se ve antes de gastar**: «te quedan 7 de 10 este mes» (y las compradas aparte, si las hay).
- **Al agotarse se explica**: el interruptor se apaga y el texto dice qué hacer — comprar
  lecturas sueltas o subir de plan — aclarando que el lector normal sigue funcionando.
- **Los planes salen de la base** (nombre, precio, lecturas y consultas), así que cambiar el
  catálogo no toca la pantalla.
- Y el camino de IA ahora acepta **PDF protegido** con la contraseña (las facturas electrónicas
  suelen venir así), igual que el lector normal.

Tests: **299 en verde** (1 nuevo).

### v1.74 — El archivo se guarda 7 días, y la IA se pide **desde la factura**

Cambio de flujo, como pediste: primero se lee con el lector normal (gratis) y **solo si la
lectura quedó dudosa** se ofrece la IA, en la propia factura. Antes el interruptor estaba antes
de subir, y como el archivo se sube al elegirlo, para cuando lo veías ya era tarde.

- **El archivo se guarda con retención limitada** (por plan: 30 archivos / 7 días / 60 MB en el
  Básico; 100/30/200 en Personal; 300/90/600 en Pro), detrás de una **abstracción de
  almacenamiento**: la ruta sale de configuración, así que en la máquina definitiva es otro
  disco y mañana podría ser un almacén de objetos sin tocar la app.
- **Un trabajo programado borra lo vencido** cada 12 h, y el usuario puede borrar el archivo
  cuando quiera desde la factura (la factura y su lectura se quedan).
- **Si el plan no da para más, la factura se sube igual**: solo se pierde la relectura, y el
  aviso lo dice.
- **«🤖 Leer con IA» dentro de la factura**: destacado en ámbar cuando la lectura es dudosa (sin
  monto, o un mercado sin artículos), discreto el resto del tiempo, con las lecturas que quedan
  a la vista. **Reemplaza** la lectura de esa misma factura: no crea otra, y **no toca** lo que
  ya estaba registrado ni lo que añadiste a mano.
- La cabecera muestra el cupo completo: lecturas, archivos guardados, MB y días de retención.

Tests: **307 en verde** (8 nuevos).

### v1.75 — El asistente: responde con las reglas de Konta (fase A, solo lectura)

Un chat dentro de la app que contesta **cualquier** pregunta sobre la aplicación y sobre las
finanzas del usuario. Lo que lo hace fiable es una regla: **el modelo no sabe los números**.

- **Diez herramientas** que llaman a los **mismos servicios que usan las pantallas**
  (`reportes.panel`, `saldos.saldo_cuenta`, `reporte_categorias`, `reporte_mensual`, tarjetas,
  presupuestos, facturas, plan y el manual de ayuda). Por eso lo que responde coincide con lo
  que se ve: no hay dos verdades.
- **No inventa**: si el dato no está en ninguna herramienta, lo dice. Y cada respuesta trae
  **qué herramientas usó**, para poder comprobarla.
- **No puede ver a otro cliente**: cada herramienta lee con la sesión del usuario que pregunta
  (hay un test que lo comprueba con dos usuarios).
- **Ayuda paso a paso**: un manual de 10 temas (registrar un gasto, subir una factura, leer con
  IA, separar casa y apartamento, presupuestos, tarjetas, planes…) que responde con pasos
  numerados y el nombre de la pantalla.
- **Acotado y medido**: máximo 4 vueltas de herramientas por pregunta, el cupo se comprueba
  **antes** de llamar al modelo, la consulta se cobra **solo si sale bien**, y cada pregunta
  queda registrada (pregunta, herramientas, tokens y coste) para el informe de promedios.
- **Es de solo lectura**: no registra ni cambia nada. Si se lo piden, dice dónde se hace (las
  acciones con confirmación son la fase siguiente).

`POST /asistente/preguntar`, más `GET /asistente/sugerencias` y `GET /asistente/manual`.

Tests: **317 en verde** (8 nuevos).

### v1.76 — El chat del asistente, dentro de la app (fase B)

El servicio ya respondía; ahora tiene cara. Página **Asistente** en el menú (Herramientas → 💬):

- **Caja de pregunta** con respuestas en el hilo, estado «Consultando tus datos…» (tarda unos
  segundos: es un modelo de verdad) y **preguntas sugeridas** para arrancar.
- **Cada respuesta dice qué consultó** («Consultó: tu resumen del mes, tus gastos por
  categoría»), que es lo que permite comprobarla contra la pantalla correspondiente.
- **El contador a la vista**: «Te quedan N de 10 consultas este mes» y, al agotarse, el aviso con
  la opción de subir de plan.
- Los errores se explican en el propio hilo (cupo agotado, sin configurar…) en vez de quedarse
  en blanco.
- Dos honestidades en la pantalla: **cada pregunta es independiente** (no recuerda la anterior) y
  las respuestas pueden equivocarse — si una cifra no cuadra, está su pantalla al lado.

Un detalle que corregí al revisarlo: la página enseñaba el **coste en tokens** de cada respuesta.
Eso lo pagamos nosotros, no el cliente: se quitó de la pantalla (el gasto se sigue midiendo por
dentro, para el informe de promedios).

Tests: **317 en verde** (sin cambios en el backend; CI incluido).

### v1.77 — El espacio se mide en MB-día (y deja de ser una foto)

Para poder cobrar el almacenamiento con criterio había que medirlo como se mide de verdad: no es
lo mismo guardar 30 archivos una semana que un mes entero.

- **Un trabajo diario** (23:50 en Colombia) suma al mes en curso lo que ocupan los archivos de
  cada usuario: **archivos-día** y **MB-día**. Es **idempotente**: si corre dos veces el mismo
  día, el cliente no paga dos veces (queda anotado el último día medido, y hay test).
- **La cuota lo enseña**: además de la foto de ahora (archivos y MB), el usuario ve su
  **promedio** del mes, el acumulado en MB-día y cuántos días se han medido.
- Cada mes arranca su propia cuenta, y un usuario sin archivos guardados no entra en la medición.

Con tus documentos (0,16 MB de media, 30 archivos ≈ 4,8 MB) un cliente que use la app todo el mes
acumula del orden de **150 MB-día**: es la cifra con la que se compara cada plan, y la que
alimenta el informe de promedios.

Tests: **319 en verde** (2 nuevos).

### v1.78 — El informe del mes: cuánto cuesta cada cliente y qué margen deja

La pieza que permite poner precios con datos en vez de a ojo. Junta lo que ya se mide —lecturas
con IA, consultas, tokens, coste facturado por el proveedor y **MB-día** de almacenamiento— y lo
compara con lo que pagan los clientes.

- **Promedios y percentiles (p50 y p90)** por plan, no solo la media: un cliente pesado mueve el
  promedio y casi no mueve el p50, y el p90 es el que dice cuánto cuesta el 10 % que más usa la
  app (hay un test con el caso `[1×9, 100]`: promedio 10,9 · p50 1 · p90 10,9).
- **Margen por plan**: ingreso en pesos contra coste real (en dólares, convertido con la **TRM**
  que la app ya mantiene al día). Con eso se ve si un plan deja ganancia y cuánta.
- **Honesto cuando falta un dato**: si no hay precio por GB-mes configurado, da el volumen
  consumido y **dice que falta el precio** en vez de inventar un coste.
- **Solo lo ve el dueño** (`FINANZAS_INFORME_ADMINS`): es información de todos los clientes, no de
  uno. Y las **cuentas del dueño quedan fuera**: no se pagan a sí mismas, así que no inflan el
  ingreso (se informa cuántas se excluyeron).

`GET /ia/informe?periodo=AAAA-MM`.

Tests: **324 en verde** (5 nuevos).

### v1.79 — El cobro: planes y paquetes de lecturas (núcleo, sin depender de la pasarela)

El circuito completo del dinero, con la pasarela detrás de una interfaz para enchufar Wompi,
MercadoPago o PayU cambiando una variable:

- **Catálogo en la base**: los planes ya estaban; ahora también los **paquetes de lecturas**
  (10 por $3.000 y 50 por $12.000, provisionales: se ajustan con la medición del mes).
- **El precio lo pone el catálogo, no el cliente**: el cuerpo de la petición solo acepta qué se
  compra; el monto se lee de la base (hay test que manda `monto: 1` y se ignora).
- **Idempotencia de verdad**: cada orden lleva una `referencia` que viaja a la pasarela y vuelve
  en su aviso, y la orden queda marcada como `aplicado`. Un aviso repetido —las pasarelas
  reintentan— **no vuelve a acreditar** (test con tres avisos seguidos: las lecturas suben 10,
  no 30).
- **Nada se acredita sin pago**: el plan o las lecturas solo se suman cuando el pago queda
  `pagado`, y queda anotado cuándo y con qué identificador de la pasarela.
- **Recibos e historial**: `GET /pagos/mios` devuelve qué compró, cuánto y cuándo.
- **Sin agujeros**: con una pasarela real, el aviso se autentica con **su firma**; con la
  **simulada** (que no tiene firma) el aviso **exige sesión**, porque si no cualquiera con una
  referencia podría acreditarse lecturas. Y la confirmación simulada no existe si hay una
  pasarela real configurada.

`GET /pagos/paquetes`, `POST /pagos/orden`, `POST /pagos/webhook/{pasarela}`, `GET /pagos/mios`.

**Falta enchufar la pasarela real** (necesita tus credenciales y su documentación: desde este
entorno no se alcanza la de Wompi, y no invento su API). Queda registrado como tarea siguiente.

Tests: **335 en verde** (11 nuevos).
