# Estado del plan de IA y planes

Última revisión: **30 de septiembre de 2026**. Este documento dice qué está hecho, qué está
verificado y qué falta — y por qué.

## Resumen en una línea

**Todo el plan está implementado, desplegado y verificado en producción** ✅, salvo **dos piezas que
necesitan algo que solo puedes dar tú**: la **máquina de 500 GB** y tus **llaves de comercio** para
la pasarela real.

## Lo que está hecho y verificado

| # | Tarea | Estado | Cómo se comprobó |
|---|---|---|---|
| 1 | Medir el almacenamiento (MB-día) | ✅ | El trabajo diario midió 2 usuarios y no repitió el mismo día; la cuota enseña promedio, MB-día y días medidos |
| 2 | Informe de promedios y margen | ✅ | Con tus datos reales: 0 clientes, 0 cobrado, 2 cuentas del dueño fuera, TRM 3.341,23 y las notas de lo que falta |
| 3 | Cobro de planes y lecturas | ✅ núcleo | Circuito completo verificado: el precio lo pone el catálogo, un aviso repetido no acredita dos veces y el aviso simulado sin sesión da 401 |
| 4 | Ayuda paso a paso con embeddings | ✅ | Con el asistente real: encontró «meta de ahorro» por **significado** (las palabras no coincidían) y dijo «no lo tengo» ante algo que no está |
| 5 | Informes a pedido | ✅ | Comparación de dos meses contra el panel: las cifras cuadraron al peso, y fue honesto con el porcentaje que no tenía |
| 6 | Acciones con confirmación | ✅ | Con el modelo real: propuso (sin registrar nada), resolvió «ayer», no inventó una etiqueta que no existe y al confirmar dos veces no duplicó |
| 7 | PDFs ilimitados con tope de peso | ✅ | Subió **33 documentos** donde el Básico se queda en 30, y el aviso habla de peso y de días |
| 8 | Panel de coste real y margen | ✅ | Encontró a un cliente que **paga 6.000 y cuesta 10.024** (margen −67 %) que el promedio del plan (16,41 %) escondía |
| 9 | Migración a la máquina definitiva | ⏳ | Procedimiento, scripts y **restauración real comprobada** («la copia es fiel: los números cuadran»); falta la máquina |

## Lo que falta, y por qué

| Qué | Qué necesita | Cuánto cuesta hacerlo |
|---|---|---|
| **Pasarela real** | Tus llaves de comercio (Wompi, MercadoPago o PayU) y su documentación | Implementar tres funciones en `app/pasarelas.py` (`crear_pago`, `verificar`, `interpretar`) y probarlo en sandbox. El hueco está preparado y el circuito ya funciona con la pasarela de prueba |
| **Migración** | La máquina de 500 GB | Una hora: `scripts/respaldo.sh` → `scripts/restaurar.sh` → `scripts/verificar_migracion.py` (paso a paso en `docs/migracion.md`) |
| **Separar la IA en su servicio** | Volumen: su propio criterio dice «cuando lo pida», y hoy no lo pide | No hacerlo todavía es la decisión correcta |

## Cómo se comprueba que sigue bien

```bash
python scripts/aceptacion.py --base http://<ip>:8082/api --web http://<ip>:8082 \
  --dsn "postgresql+psycopg://finanzas:finanzas@<ip>:5433/finanzas" --disco /
```

23 comprobaciones contra la app de verdad: incluye **que lo desplegado sea el código** ✅ (una vez
pilló un despliegue fantasma ✅) y el **espacio en disco** ✅ (una vez se llenó y los despliegues
fallaban en silencio ✅). Borra lo que crea, incluidos los archivos.

## Lo que se aprendió por el camino (y quedó arreglado)

Estas son las familias de fallos que aparecieron **revisando lo que ya estaba en producción**, no
escribiendo código nuevo. En las tres, el último caso era el más dañino porque **no se veía**:

1. **Un ajuste que no mandaba** (dos veces): el tope de tamaño decía 15 MB y otro trozo de código
   rechazaba a los 10. Regla: **un límite, y en los ajustes**.
2. **Comprobar en un sitio y escribir en otro** (cuatro veces): avisos de pago en paralelo, la cuota
   de la IA, el tope del almacén y confirmar una propuesta dos veces. Regla: **garantizar, no
   comprobar** (reservar la fila).
3. **Fechas en UTC enseñadas como días** (cuatro veces): el informe del dinero, los recibos, la
   caducidad y la fecha que se pre-rellena. Regla: **la app piensa en Colombia**.
4. **Montos mal leídos** (tres veces): `45000.5` se volvía 450.005 y `"45.000"` se guardaba como
   **45**. Regla: **una sola forma de leer dinero** (`app.dinero.parsear_monto`).

Y una lección de método, la más útil de todas: **sustituir una función también sustituye sus
promesas**. Cuando un test falla contra un stub, la primera pregunta no es qué código falta, sino si
la función de verdad ya lo evita.

## Deudas anotadas (fuera de este plan)

- **Límite de intentos en el login** y en los endpoints que gastan dinero (asistente, lectura con
  IA): riesgo real, registrado como tarea aparte.
- **Precios provisionales**: los planes y los paquetes de lecturas se ajustan con el informe de
  promedios cuando haya uso real (hoy tu cuenta no ha consumido IA).
