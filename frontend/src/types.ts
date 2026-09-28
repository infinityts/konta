export interface Categoria {
  id: string
  nombre: string
  tipo: 'ingreso' | 'gasto'
  icono: string | null
  color: string | null
}

export interface Tarjeta {
  id: string
  nombre: string
  banco: string | null
  tipo: 'credito' | 'debito'
  moneda: string
  dia_corte: number | null
  dia_pago: number | null
  limite: number | string | null
  tasa_interes: number | string | null
  activa: boolean
}

export interface Suscripcion {
  id: string
  nombre: string
  monto: number | string
  moneda: string
  periodicidad: string
  fecha_inicio: string | null
  proximo_pago: string | null
  categoria_id: string | null
  tarjeta_id: string | null
  estado: string
  notas: string | null
}

export interface Transaccion {
  id: string
  tipo: 'ingreso' | 'gasto'
  monto: number | string
  moneda: string
  fecha: string
  descripcion: string | null
  categoria_id: string | null
  tarjeta_id: string | null
  suscripcion_id: string | null
  etiqueta_id: string | null
  notas: string | null
}

export interface Etiqueta {
  id: string
  nombre: string
  color: string | null
  padre_id: string | null
}

export interface Alerta {
  tipo: 'suscripcion' | 'tarjeta_pago' | 'tarjeta_corte'
  titulo: string
  fecha: string
  dias_restantes: number
  monto: number | string | null
  moneda: string | null
}

export interface ReporteMes {
  mes: string
  ingresos: number
  gastos: number
  balance: number
}

export interface ReporteCategoria {
  categoria: string
  tipo: 'ingreso' | 'gasto'
  total: number
}

export interface IngresoRecurrente {
  id: string
  nombre: string
  monto: number | string
  moneda: string
  periodicidad: 'diario' | 'semanal' | 'mensual'
  dia: number | null
  proxima_ejecucion: string
  categoria_id: string | null
  activa: boolean
}

export function fmtMoney(v: number | string | null | undefined): string {
  const n = Number(v)
  if (!Number.isFinite(n)) return '—'
  return `$${n.toLocaleString('es-CO', { minimumFractionDigits: 0, maximumFractionDigits: 2 })}`
}
