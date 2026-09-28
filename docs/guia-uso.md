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
