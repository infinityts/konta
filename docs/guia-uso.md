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

## 3. Categoría vs. Etiqueta (esto confunde a todos)

| | **Categoría** | **Etiqueta** |
|---|---|---|
| Responde | **¿Qué** es? | **¿Para qué / de quién** es? |
| Ejemplos | Vivienda, Mercado, Transporte | Hogar, Trabajo, Reembolsable |
| ¿Jerárquica? | Sí → **subcategorías** (`Transporte › Gasolina`) | Sí → **subetiquetas** (`Hogar › Internet`) |
| Para qué sirve | Reportes, presupuestos | Cruzar gastos de varias categorías |

Un gasto tiene **una** categoría y **una** etiqueta. Ejemplo:

> Internet Movistar → categoría `Vivienda › Internet`, etiqueta `Hogar › Servicios`

**Crear:** en el propio formulario del movimiento hay un botón
**＋ Nueva etiqueta / subetiqueta** (eliges si es principal o subetiqueta de otra).
Para categorías, usa la página **Categorías**.

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

**Top categorías** — los gastos del mes por `Categoría › Subcategoría`.

---

## 6. Consolidado y reportes

| Página | Para qué |
|---|---|
| **Cuentas** → *Consolidado mes a mes* | Saldo inicial, ingresos, gastos, balance y **saldo final corrido** |
| **Reportes** | Evolución de 6 meses y desglose por categoría → subcategoría |
| **Presupuestos** | Límite mensual por categoría, % consumido y aviso de exceso |
| **Flujo** | Proyección a 3/6/12 meses con recurrentes y suscripciones |
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
