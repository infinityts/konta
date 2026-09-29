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
