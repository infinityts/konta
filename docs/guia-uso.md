# Guía de uso de Konta

Guía práctica, en orden. Si haces estos pasos, la app te sirve de verdad.

---

## 1. Lo primero: crea tus cuentas con el saldo inicial

**Sin esto, el saldo que ves es solo el flujo de tus movimientos, no tu dinero.**

👉 **Cuentas** → *Nueva cuenta*

| Campo | Qué poner |
|---|---|
| Nombre | `Efectivo`, `Banco Bogotá`, `Ahorros`… |
| Tipo | efectivo / banco / ahorro / otro |
| Saldo inicial | **el dinero que tienes HOY en esa cuenta** |

Puedes tener varias. El **saldo total** es la suma.

> La app calcula: `saldo = saldo inicial + ingresos − gastos`.
> Si tu cuenta quedó con movimientos viejos, usa **«Asignar movimientos sin cuenta»**.

---

## 2. Cada movimiento va a una cuenta

👉 **Transacciones** → *Nueva transacción* → elige la **Cuenta**.

- Si solo tienes una cuenta, se selecciona sola.
- Si guardas sin cuenta, la app te avisa: ese movimiento **no** moverá el saldo.

Todo se puede corregir después con el botón **Editar**.

---

## 3. Categoría → Etiqueta → Subetiqueta

**Las etiquetas viven DENTRO de una categoría.** Son tres niveles:

```
CATEGORÍA          ETIQUETA         SUBETIQUETA
─────────          ────────         ───────────
Casa 1     ──────► Servicios  ─────► Internet
                   Aseo       ─────► Señora
                   Arriendo

Casa 2     ──────► Servicios  ─────► Internet      ← ✅ otra categoría
```

| Nivel | Responde | Ejemplos |
|---|---|---|
| **Categoría** | ¿En qué contexto? | `Casa 1`, `Casa 2`, `Trabajo` |
| **Etiqueta** | ¿Qué tipo? | `Servicios`, `Aseo`, `Arriendo` |
| **Subetiqueta** | ¿Cuál exactamente? | `Internet`, `Agua`, `Señora` |

### La regla: únicos entre hermanos

> Dos nombres iguales **no pueden ser hermanos** (mismo padre), sin importar
> mayúsculas. En **padres distintos** sí se pueden repetir.

| Intento | ¿Se permite? |
|---|---|
| `Casa 1 › Servicios` y luego otra `Casa 1 › Servicios` | ❌ Ya existe en esa categoría |
| `Casa 1 › Servicios › Internet` y otra igual | ❌ Ya existe en esa etiqueta |
| `Casa 1 › Servicios › Internet` y `Casa 2 › Servicios › Internet` | ✅ Padres distintos |
| Categoría `Vivienda` y luego otra `Vivienda` | ❌ Ya existe |
| `Vivienda › Internet` y `Transporte › Internet` | ✅ Padres distintos |

**Al registrar un movimiento** se elige en cascada: primero la **categoría**, y el selector
de etiquetas muestra **solo las de esa categoría**. Si eliges otra categoría, la etiqueta
se limpia (no puede quedar una etiqueta de otra categoría).

**Crear:** en el formulario del movimiento (botón **＋ Nueva etiqueta / subetiqueta**, que usa
la categoría elegida) o en la página **Etiquetas**, que está agrupada por categoría.

---

## 4. Tarjetas de crédito

👉 **Tarjetas** → *Nueva tarjeta*

| Campo | De dónde sale |
|---|---|
| Nombre / Banco | `AMEX Platinum` / `Bancolombia` |
| Tipo | Crédito o Débito |
| **Cupo total** | **cupo disponible + deuda** (no el disponible) |
| Día de corte | el del extracto |
| **Día de pago** | el del extracto (⚠️ no confundir con el corte) |
| **Tasa** | del extracto → ver abajo |

### Débito vs. crédito (el concepto contable)

| | **Débito** | **Crédito** |
|---|---|---|
| Qué es | **Instrumento** de una cuenta | **Pasivo**: plata que debes |
| ¿Tiene saldo propio? | No — el saldo es el de **su cuenta** | Sí: su **deuda** |
| En Konta | Se **asocia a una cuenta** | No se asocia a ninguna cuenta |
| Un gasto con ella | Descuenta de **su cuenta** | No toca tus cuentas (sube la deuda) |

**Caso típico:** tienes una cuenta de ahorros donde llega el salario y una **tarjeta débito**
de esa misma cuenta. La tarjeta **no es un saldo aparte**, es la *llave* de la cuenta.

Entonces:

1. Crea **una sola** cuenta: `Ahorros Bancolombia` con su saldo inicial.
2. Crea la tarjeta **débito** y **asóciala** a esa cuenta (el formulario lo pide).
3. Al registrar un gasto, elige la tarjeta débito → **la cuenta se llena sola** y su saldo baja.

Si en cambio crearas la tarjeta débito como una cuenta separada, **contarías tu plata dos veces**.

**Con el crédito es distinto:** es un pasivo. Un gasto con la tarjeta de crédito **no** baja tu
cuenta de ahorros (todavía no has pagado); lo que sube es la **deuda** de la tarjeta — y esa la
registras desde el extracto (ver *Registrar la deuda*).

### La tasa: cuidado con la escala

Los extractos colombianos publican la **tasa efectiva anual (E.A.)**, y en la misma
tabla su equivalente **mes vencido**. Ejemplo real:

| | Mes vencido | Efectivo anual |
|---|---|---|
| Compra Internacional | 2.1593 % | **29.2215 %** |

En el formulario usa el **selector**:

- **E.A. (% anual)** → escribe `29.2215` ← **recomendado**, es lo que dice el banco
- **Mensual (%)** → escribe `2.1593`

La app convierte con `(1 + EA)^(1/12) − 1`. **No** divides entre 12: eso da 2,4351 %
en vez de 2,1593 % y sobreestima el interés.

> ⚠️ Si escribes `2.1593` en el campo de **E.A.**, la app lo rechaza avisando. Si lo
> escribieras en la escala equivocada, verías cosas imposibles como
> *"intereses de $19.245.444 al mes"*.

### Registrar la deuda

👉 **Tarjetas** → **Registrar deuda** → moneda + monto, una vez por cada moneda.

- Una tarjeta puede deber en **varias monedas** (ej. `COP 8.912.816` + `USD 700`).
- Si registras la tasa de cambio en **Monedas** (ej. TRM `USD → COP` = `3329.61`),
  verás el **total consolidado en COP**.
- El **simulador** usa esa deuda automáticamente si dejas el saldo vacío.

### Simulador de intereses

Elige la tarjeta, deja el saldo vacío (usa la deuda registrada) y opcionalmente un pago
mensual. Te dice **meses para pagar**, **total de intereses** y **total pagado**.

Si el pago no cubre los intereses, te lo dice y **la deuda nunca baja**.

---

## 5. Leer el dashboard

**Saldo actual** — tu dinero real (con cuentas configuradas).

Si aparece **SOBREGIRADO** en rojo, debajo vienen los **motivos**:

- Que no tienes cuentas (el saldo es solo flujo).
- El déficit del mes (gastos vs ingresos).
- La categoría que más te consumió.
- Tus suscripciones activas (gasto fijo).
- Movimientos sin cuenta asignada.
- Un ingreso recurrente que **aún no llega** (ej. el salario del día 30).

**Balance de <mes>** — solo el mes en curso (ingresos − gastos).

**Top categorías** — los gastos del mes por `Categoría › Etiqueta › Subetiqueta`.

---

## 6. Consolidado y reportes

| Página | Para qué |
|---|---|
| **Cuentas** → *Consolidado mes a mes* | Saldo inicial, ingresos, gastos, balance y **saldo final corrido** |
| **Reportes** | Evolución de 6 meses y desglose por `Categoría › Etiqueta › Subetiqueta` |
| **Presupuestos** | Límite mensual por categoría, % consumido y aviso de exceso |
| **Flujo** | Proyección a 3/6/12 meses con ingresos recurrentes, suscripciones **y pólizas** (en COP) |
| **Metas** | Objetivos de ahorro con aportes y aporte mensual sugerido |

---

## 7. Notificaciones

👉 **Notificaciones** → activa, elige canal (**Telegram**, **correo** o ambos),
días de anticipación y destino. Botón **Enviar prueba**.

- **Telegram**: crea un bot con **@BotFather**, define `FINANZAS_TELEGRAM_BOT_TOKEN`
  en el servidor, escríbele algo al bot y pulsa **Detectar**.
- **Correo**: define las variables `FINANZAS_SMTP_*` (ver
  [`despliegue.md`](despliegue.md)).

Se envía **como máximo un resumen al día**.

---

## 8. Errores comunes

| Síntoma | Causa y solución |
|---|---|
| «Saldo negativo» sin haber gastado tanto | No hay cuentas con saldo inicial → créalas |
| El gasto no cambia el saldo | El movimiento quedó **sin cuenta** → Editar y asígnale una |
| «Intereses de millones al mes» | La tasa se guardó ×100 → Editar la tarjeta y usa **E.A. (% anual)** |
| No veo un botón nuevo | Caché del navegador → **Ctrl + Shift + R** |
| «Ingresos: $0» pero tengo salario | El ingreso recurrente aún no llega (revisa la fecha en el dashboard) |

---

## 9. Respaldo

👉 **Respaldo** → **Respaldo completo (JSON)** o **Transacciones (CSV)**.
**Restaurar** reemplaza tus datos por los del archivo (úsalo solo para recuperar).

A nivel de servidor también puedes hacer `pg_dump` (ver [`despliegue.md`](despliegue.md)).

---

## 10. Mover dinero entre tus cuentas

👉 **Transacciones** → tipo **Transferencia entre cuentas** → *Desde* una cuenta y *Hacia* otra.

- **No es un gasto ni un ingreso**: no aparece en reportes, presupuestos ni flujo de caja. Es
  dinero que cambia de sitio, no dinero que se va.
- Las dos cuentas tienen que ser tuyas y estar en la **misma moneda**; si no, la app lo dice en
  vez de inventarse la conversión.
- En **Cuentas** verás `− transferencia` y `+ transferencia` en cada cuenta, para que el saldo
  cuadre a la vista.

> Regla práctica: si el dinero **sigue siendo tuyo** (pasarlo a ahorros, recargar la cuenta del
> día a día), es una **transferencia**. Si **se va** (mercado, arriendo), es un **gasto**.

---

## 11. Pagar la tarjeta de crédito

👉 **Tarjetas** → en tu tarjeta de crédito, botón **«Pagar tarjeta»** → elige **de qué cuenta
sale**, el monto (viene ya puesto con lo que debes) y Pulsa **Pagar**.

Qué hace la app:

| | |
|---|---|
| Baja el saldo de la **cuenta** | el dinero salió de verdad de ahí |
| Baja la **deuda** de la tarjeta | queda el remanente si el pago fue parcial |
| **No** lo cuenta como gasto | el consumo ya se contó cuando compraste |

**La deuda vigente** que ves es: *lo que dice el último extracto* **−** *los pagos hechos
después de ese extracto*. Por eso:

- Si registras el extracto de octubre, **reemplaza** al de septiembre (no se suman).
- Si ya pagaste y luego registras el extracto nuevo, **no se resta dos veces**: ese extracto ya
  incluye el pago, así que pasa a ser el punto de partida.

**Si te equivocaste**: el pago aparece en la tarjeta con **«deshacer»**, que lo quita y devuelve
el dinero a la cuenta.

> **Ojo con el orden**: registra primero el extracto y luego el pago. Si intentas pagar sin deuda
> registrada, la app te lo dice en vez de dejarte con un saldo a favor raro.

---

## 12. Un gasto que se repite todos los meses

Para el arriendo, el colegio, el streaming o los servicios: no hace falta ir a otra pantalla.

👉 **Transacciones** → **Nueva transacción** → llena monto, fecha, categoría y **la cuenta** →
en el selector elige **«se repite… cada mes»** (o cada semana, trimestre, semestre, año) →
Guardar.

Qué hace la app:

| | |
|---|---|
| Guarda **este** movimiento | con su cuenta, así que el saldo de este periodo ya está bien |
| Crea el **compromiso recurrente** | con el mismo monto, categoría, etiqueta, cuenta y tarjeta |
| Lo apunta al **periodo siguiente** | **el día sale de la fecha** que pusiste: si fue el 5, el próximo es el 5 del mes que viene |
| Y desde ahí lo genera **solo** | cada vez que toca, sin que vuelvas a registrarlo |

El listado marca esos movimientos con **🔁 recurrente**, para que distingas los que vinieron
solos de los que tecleaste.

**Si te equivocaste**: en el grupo **Recurrentes** → *Gastos recurrentes* puedes editar el
compromiso, **pausarlo** (deja de generar sin borrar el historial) o eliminarlo. Quitar el
compromiso **no** borra los movimientos que ya generó.

**Ocasional vs recurrente**: una compra de ropa es ocasional (una sola vez); el arriendo es
recurrente. Si dudas: ¿volverás a pagarlo el mes que viene por el mismo monto? Entonces es
recurrente.

---

## 13. Casa 2 con las etiquetas de Casa 1

Si vas a llevar dos viviendas (o dos coches, o dos negocios), no hace falta volver a teclear
el mismo árbol.

👉 **Categorías** → en la fila de la categoría nueva, **«Copiar etiquetas de…»** → elige el
origen.

1. Al elegir el origen la app **enseña el plan**: «se crearán 6 etiqueta(s): Servicios ›
   Internet, Servicios › Agua, Aseo › Señora del aseo…». Todavía **no ha tocado nada**.
2. Pulsa **Copiar**. Se crean las etiquetas y subetiquetas, conservando el anidamiento.
3. Lo que ya existía **no se duplica**: si la categoría nueva ya tenía «Servicios» pero no sus
   hijas, se añaden las hijas.

**Por qué copiar y no compartir**: cada categoría tiene sus propias etiquetas. Si renombras
«Internet» en Casa 1, Casa 2 no cambia. Compartir una misma etiqueta entre dos categorías
dejaría los reportes sin saber a cuál asignar el gasto.

> Truco: como el OCR clasifica por **nombres de etiquetas**, copiar el árbol en vez de
> inventar nombres nuevos («Internet Casa 2») hace que la tira del súper y las facturas de
> servicios se sigan clasificando solas en la casa que corresponda.

---

## 14. Seguros y pólizas

👉 **Seguros** → *Nueva póliza*

| Campo | Qué poner |
|---|---|
| Tipo | `Vida`, `Salud`, `Vehículo`, `Hogar` u `Otro` |
| Aseguradora | Sura, Bolívar, Colsanitas… |
| Persona asegurada | Quién queda cubierto (en vehículo, el tomador) |
| Placa / marca / modelo / año | **Solo si el tipo es Vehículo** (el formulario los muestra entonces) |
| Valor asegurado | Lo que pagaría el seguro si hay siniestro |
| Prima y periodicidad | Lo que pagas y cada cuánto (`mensual`, `trimestral`, `semestral`, `anual`) |
| Inicio / fin de vigencia | El periodo cubierto |
| Renovación automática | Márcala si el seguro se renueva solo: así no te avisa del vencimiento |
| Próximo pago de prima | Cuándo se cobra la siguiente. **Al llegar esa fecha, la app crea el gasto sola** |
| Categoría / etiqueta / tarjeta / cuenta | Dónde cae el gasto y de dónde sale el dinero |

**Lo que hace la app por ti:**

- Genera el **gasto de la prima** al vencer (un job cada hora, idempotente: no duplica).
- Te **avisa** de la prima próxima y del **fin de vigencia** en el dashboard.
- Suma el **costo de los seguros**: prima al mes y al año, normalizada a COP (una póliza
  anual de 600.000 pesa 50.000 al mes, no 600.000).
- Si la póliza está en otra moneda y no hay tasa registrada, te lo dice **en vez de sumar
  mal**: regístrala en **Monedas**.

**Personas cubiertas** (botón *Personas cubiertas* en la póliza): en una póliza familiar
añade a cada persona con su parentesco y fecha de nacimiento, y marca **quién es el titular**
(solo puede haber uno). El campo *Persona asegurada* de la póliza sigue siendo la principal,
la que da el nombre a la póliza.

**Beneficiarios** (típico en seguros de vida): en el mismo panel → nombre, parentesco y
**porcentaje**. Los porcentajes **no pueden sumar más de 100**; la app te dice cuánto suman
si te pasas.

> Para **pausar** un seguro (por ejemplo, un vehículo vendido) usa *Pausar*: deja de generar
> el gasto y de avisar, pero conserva el histórico.

---

## 15. Leer un extracto del banco (tarjeta o cuenta)

👉 **Extractos** → elige el archivo (**PDF o Excel**) → si el PDF tiene contraseña, escríbela →
**Leer extracto**.

| Paso | Qué pasa |
|---|---|
| 1. Subes el archivo | Se lee el **PDF por coordenadas** (cada valor cae en su columna) o el **Excel hoja por hoja** |
| 2. Konta lo lee | Saca el periodo, el corte, el pago total, el pago mínimo, el cupo y cada movimiento, con sus cuotas |
| 3. **¿Cuadra?** | Compara lo leído con lo que **dice el banco**. Si no cuadra, lo dice y señala los movimientos dudosos |
| 4. Miras el análisis | Compras, pagos, **costo del dinero** (intereses + comisiones), cupo usado, a dónde se fue la plata y el **compromiso futuro** de las compras a cuotas |
| 5. Revisas el detalle | La tabla de movimientos, con su tipo (compra, pago, interés, comisión…) y las compras en dólares con su tasa |

### Importar los movimientos a Konta

Cuando el análisis te convenza, la misma página trae **Importar a Konta**:

| Qué | Cómo se decide |
|---|---|
| Se importa | Lo que te facturan **este** mes: cada compra (a cuotas, **por la cuota del mes**), los intereses y las comisiones |
| También entra | La **cuota de este mes** de las compras de meses anteriores: es plata que sale ahora y es lo que hace que cuadre con el pago mínimo |
| No se importa | El **valor completo** de una compra de meses anteriores (ya se contó cuando la compraste), los **ajustes** (suman y restan lo mismo) y los **pagos** (pagar lo tuyo no es un gasto) |
| Si falta la cuota | La fila **no** se importa y se dice por qué: ni el valor completo (inflaría el mes) ni la mitad |
| Dos veces | Nada se duplica: un movimiento ya importado se salta y lo dice |

La previsualización te dice **cuánto suma** lo que se va a importar y lo compara con el
**pago mínimo del corte**. Cuando coincide, es que el mes está bien: en los extractos reales
probados, Davivienda importa **353.076,89** (su pago mínimo exacto) y Amex **956.314,13**
frente a 956.315,00 (el banco redondea).

Al importar, el **cupo utilizado** del corte queda registrado como deuda de la tarjeta, y el
**pago total** aparece en las alertas con la fecha límite que dice el extracto.

> Nada entra en tus cuentas sin que lo hayas visto: primero el análisis, después la
> previsualización con lo que se omite y por qué, y solo entonces el botón.

### Recurrentes detectados

Debajo del análisis, Konta propone lo que **se repite todos los meses** y lo explica:

| Señal | Qué significa |
|---|---|
| **Repetición entre extractos** | El mismo comercio en dos cortes, a ~1 mes y con el mismo monto → confianza **alta** |
| **Ya estaba en tus movimientos** | Lo llevabas pagando de antes, aunque solo tengas un extracto leído |
| **Diccionario de servicios** | Netflix, Spotify, Prime Video, iCloud, ChatGPT… Un servicio **nuevo** aparece una sola vez en su primer extracto, así que sin esta señal no se vería |
| **A cuotas no** | Una compra a 24 cuotas **nunca** es una suscripción (RAPPI aparece 7 veces en un extracto real y no lo es) |
| **Diferida, con la cuota** | Si el banco difiere una suscripción a cuotas (Amex difiere Audible a 36), se propone con **la cuota** como monto |

Los candidatos vienen marcados con su confianza, con las fechas de los cargos y con el
**próximo pago calculado**. Se eligen con una casilla y se crean en *Gastos recurrentes*; los
que ya existían se omiten en vez de duplicarse. Dos cargos del mismo servicio el mismo día
(Prime Video 17.999 y 4.999) se proponen como **dos planes**, no como uno doble.

- **Lo anterior al periodo no es un gasto nuevo**: los extractos listan el capital de compras de
  meses atrás. Esas filas se marcan *informativas* y se pueden ocultar (casilla de la tabla).
- **Una compra a cuotas no es una suscripción**: `7 de 24` significa que ya la estabas pagando.
  El detalle trae la cuota del mes y lo que queda pendiente.
- **Multi-moneda**: si el extracto trae pesos y dólares (Amex), cada movimiento se guarda **en su
  moneda** y el análisis muestra el desglose al lado. No se convierte nada al guardar: la
  conversión es de presentación y, si falta la tasa, se avisa en vez de inventarla.
- Si el extracto es de una **cuenta** (ahorros o corriente), dilo en el desplegable *Tipo*.

---

## 16. Cuánto debo, cuánto me cuesta y si cuadra (deuda y cuotas)

👉 **Deuda y cuotas** (junto a Extractos). Mira todos tus extractos juntos.

| Bloque | Qué dice |
|---|---|
| **Compromiso futuro** | Lo que ya compraste a cuotas y te falta pagar: el capital pendiente, la cuota de este mes y **mes a mes** los próximos 6/12/24 meses. Cada moneda por separado |
| **Compra por compra** | Valor, cuota, cuántas van, cuántas faltan, pendiente y la **tasa E.A.** de cada compra |
| **Costo del dinero** | Intereses, comisiones e impuestos de cada extracto y **qué parte de lo que pagas se va en eso** |
| **Simulador con la tasa real** | La tasa no es la que tengas configurada: es el **promedio ponderado por capital pendiente** de las tasas del extracto. Dice de dónde la sacó, en cuántos meses terminas y cuánto pagas de intereses |
| **Auditoría** | Si lo que dice el banco cuadra con lo que tienes registrado: lo importado contra el pago mínimo del corte, si falta algo por importar y si hay movimientos repetidos |

> La **tasa real** sale del extracto (`1,9648% 26,30%` son la mensual y la anual; se toma la
> anual) ponderada por el capital pendiente: la deuda cara pesa más que la barata. Si el
> extracto no la trae, se usa la de la tarjeta y se dice que es esa.

---

## 17. Subir un recibo (OCR por línea)

👉 **Facturas** → sube el **PDF o una foto** del recibo → botón **Leer líneas**.

| Paso | Qué pasa |
|---|---|
| 1. Subes el archivo | Se extrae el texto (OCR si es una foto, con preprocesado) y se detectan monto y fecha |
| 2. **Leer líneas** | Parte el recibo en artículos y los clasifica: `historial` → `diccionario` → `embeddings` |
| 3. Revisas la tabla | Cada línea trae su etiqueta sugerida y de dónde salió (el *badge* de la derecha) |
| 4. Corriges lo que esté mal | Cambia la etiqueta en el desplegable: la app **lo aprende** y la próxima vez lo acierta |
| 5. Dices de dónde sale el dinero | **Tarjeta** (💳) y/o **cuenta**, y la **fecha** si el recibo es de otro día |
| 6. **Confirmar N línea(s)** | Se crea **una transacción por artículo**, con su categoría y etiqueta |
| 6b. **O «Un solo gasto»** | Se crea **una** transacción con el total y las líneas quedan como detalle suyo |

**¿Por artículo o un solo gasto?** Para la tira del súper, **por artículo**: cada cosa cae en su
etiqueta y los reportes por categoría dicen algo. Para una compra de dos o tres cosas (ropa,
tecnología), **un solo gasto**: así el listado no se llena de movimientos sueltos y la cuenta se
descuenta una vez. El bloque *«O registra todo como un solo gasto»* está en el mismo panel: toma
la cuenta, la tarjeta y la fecha de arriba, y si el total del recibo no cuadra con la suma de las
líneas te ofrece usarlo con un clic.

**Si son muchas y no quieres ir una por una**: en el bloque *«Asignar a las N sin
clasificar»* elige categoría y etiqueta y pulsa **Aplicar**. Se aplica a todas las que están
sin clasificar (lo que el diccionario ya acertó no se toca) y **cada una queda aprendida**,
así que la próxima compra de lo mismo ya sale clasificada.

**Si al confirmar queda alguna sin clasificar**: elige una **categoría de respaldo** antes de
confirmar. Si no, esas transacciones se crean **sin categoría** y no aparecerán en los
reportes por categoría ni contarán en los presupuestos.

**Si sale todo «sin clasificar»**: pulsa **«Preparar etiquetas del diccionario y volver a
clasificar»**. Crea las etiquetas que el OCR sabe reconocer (Carnes, Despensa, Ropa…) dentro
de *Mercado*, *Transporte* y *Otros gastos*. Vienen de fábrica al registrarte, así que solo
hace falta en cuentas antiguas o si borraste esas etiquetas.

**Tarjeta de débito o de crédito**: al elegir una de **débito** se rellena sola su cuenta
(la tarjeta es un instrumento de esa cuenta); al elegir una de **crédito** la cuenta se
limpia, porque ese gasto no sale de tu cuenta sino que engorda la deuda de la tarjeta.

**Artículos que la app no conoce** (una marca rara, un producto nuevo): quedan *sin
clasificar*. Asígnales la etiqueta una vez —eso queda aprendido— y la próxima tira ya sale
clasificada.

### Ver y deshacer lo aprendido

👉 **Herramientas** → **Reglas de OCR** (o el enlace «Ver lo que el OCR ha aprendido» en
*Facturas*).

Cada corrección que haces queda como una regla: *«PECHUGA POLLO BANDEJA → Mercado › Carnes»*.
Ahí puedes:

- **Ver** qué sabe y cuántas veces ha usado cada regla.
- **Corregir** una regla (el texto o la etiqueta) si aprendió algo mal.
- **Borrar** una regla: el artículo deja de reconocerse de memoria y vuelve a decidirse por el
  diccionario. Es la forma de deshacer un aprendizaje equivocado.
- **Enseñar** una regla a mano, sin esperar a que aparezca en un recibo.

> **Ojo**: el historial es lo **primero** que mira el clasificador, antes que el diccionario.
> Por eso una regla equivocada manda sobre todo lo demás — y por eso conviene revisarlas de vez
> en cuando.
