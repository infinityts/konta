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

## 10. Seguros y pólizas

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

## 11. Subir un recibo (OCR por línea)

👉 **Facturas** → sube el **PDF o una foto** del recibo → botón **Leer líneas**.

| Paso | Qué pasa |
|---|---|
| 1. Subes el archivo | Se extrae el texto (OCR si es una foto, con preprocesado) y se detectan monto y fecha |
| 2. **Leer líneas** | Parte el recibo en artículos y los clasifica: `historial` → `diccionario` → `embeddings` |
| 3. Revisas la tabla | Cada línea trae su etiqueta sugerida y de dónde salió (el *badge* de la derecha) |
| 4. Corriges lo que esté mal | Cambia la etiqueta en el desplegable: la app **lo aprende** y la próxima vez lo acierta |
| 5. Dices de dónde sale el dinero | **Tarjeta** (💳) y/o **cuenta**, y la **fecha** si el recibo es de otro día |
| 6. **Confirmar N línea(s)** | Se crea **una transacción por artículo**, con su categoría y etiqueta |

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
