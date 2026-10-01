/**
 * La fecha de **hoy**, en la zona del navegador.
 *
 * `new Date().toISOString()` da la fecha en UTC: en Colombia, a partir de las 19:00 devuelve la de
 * mañana. Eso hacía que un movimiento nuevo se pre-rellenara con el día siguiente y que el Resumen
 * pidiera el mes siguiente la última noche del mes.
 */
export function hoyLocal(): string {
  const d = new Date()
  const mes = String(d.getMonth() + 1).padStart(2, '0')
  const dia = String(d.getDate()).padStart(2, '0')
  return `${d.getFullYear()}-${mes}-${dia}`
}

/** El mes en curso (AAAA-MM) en la zona del navegador. */
export function mesLocal(): string {
  return hoyLocal().slice(0, 7)
}
