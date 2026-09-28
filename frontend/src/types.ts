export interface Categoria {
  id: string
  nombre: string
  tipo: 'ingreso' | 'gasto'
  icono: string | null
  color: string | null
}

export interface Deuda {
  id: string
  tarjeta_id: string
  moneda: string
  monto: number | string
  fecha: string
  notas: string | null
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
  tasa_interes_ea: number | string | null
  cuenta_id: string | null
  cuenta_nombre: string | null
  activa: boolean
  deudas: Deuda[]
  deuda_por_moneda: Record<string, number>
  deuda_total_cop: number | null
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
  etiqueta_id: string | null
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
  cuenta_id: string | null
  notas: string | null
}

export interface Etiqueta {
  id: string
  nombre: string
  color: string | null
  categoria_id: string | null
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
  etiqueta: string | null
  tipo: 'ingreso' | 'gasto'
  total: number
}

export interface Cuenta {
  id: string
  nombre: string
  tipo: string
  moneda: string
  activa: boolean
  saldo_inicial: number | string
  ingresos: number
  gastos: number
  saldo_actual: number
}

export interface SaldoResumen {
  saldo_total: number
  saldo_inicial_total: number
  ingresos_total: number
  gastos_total: number
  sin_cuenta: number
  sin_cuenta_movimientos: number
  sobregirado: boolean
  cuentas: Cuenta[]
}

export interface ConsolidadoMes {
  mes: string
  saldo_inicial: number
  ingresos: number
  gastos: number
  balance: number
  saldo_final: number
}

export interface Consolidado {
  meses: ConsolidadoMes[]
  saldo_actual: number
}

export interface Motivo {
  tipo: string
  etiqueta: string
  monto: number
  detalle: string | null
}

export interface ProximoIngreso {
  nombre: string
  monto: number
  fecha: string
}

export interface Diagnostico {
  saldo_actual: number
  sobregirado: boolean
  tiene_cuentas: boolean
  sin_cuenta_movimientos: number
  proximo_ingreso: ProximoIngreso | null
  ingresos_mes: number
  gastos_mes: number
  balance_mes: number
  ingresos_mes_anterior: number
  gastos_mes_anterior: number
  gastos_fijos: number
  motivos: string[]
  top_categorias: Motivo[]
}

export interface Factura {
  id: string
  nombre_archivo: string
  texto_extraido: string | null
  monto_detectado: number | string | null
  fecha_detectada: string | null
  transaccion_id: string | null
  creada_en: string
}

/** Un artículo detectado por OCR dentro de una factura. */
export interface FacturaLinea {
  id: string
  factura_id: string
  descripcion: string
  cantidad: number | string | null
  valor_unitario: number | string | null
  valor_total: number | string
  etiqueta_id: string | null
  origen: 'historial' | 'diccionario' | 'embeddings' | 'manual' | 'sin_clasificar'
  confianza: number | string | null
  orden: number
  transaccion_id: string | null
}

export interface FacturaDetalle extends Factura {
  lineas: FacturaLinea[]
  tipo_documento: string | null
}

export interface Presupuesto {
  id: string
  categoria_id: string
  categoria_nombre: string
  monto_limite: number | string
  moneda: string
  gastado: number
  restante: number
  porcentaje: number
  activo: boolean
}

export interface ImportarFila {
  fecha: string
  descripcion: string | null
  monto: number | string
  tipo: 'ingreso' | 'gasto'
  moneda: string
  categoria_id: string | null
}

export interface Producto {
  id: string
  nombre: string
  unidad: string | null
}

export interface ComparativoTienda {
  tienda: string
  precio: number | string
  moneda: string
  fecha: string
}

export interface Comparativo {
  producto_id: string
  producto_nombre: string
  tiendas: ComparativoTienda[]
  mas_barata: string | null
}

export interface ItemLista {
  id: string
  producto_id: string | null
  nombre: string
  cantidad: number | string
  precio_estimado: number | string | null
  comprado: boolean
}

export interface ListaMercado {
  items: ItemLista[]
  total_estimado: number
  pendientes: number
}

export interface Moneda {
  codigo: string
  nombre: string
  simbolo: string
}

export interface Tasa {
  id: string
  moneda_origen: string
  moneda_destino: string
  tasa: number | string
  fecha: string
  fuente: string | null
}

export interface Conversion {
  de: string
  a: string
  monto: number | string
  tasa: number | string
  resultado: number | string
}

export interface Simulacion {
  saldo_inicial: number | string
  tasa_mensual: number | string
  pago_mensual: number | string
  meses: number
  total_intereses: number | string
  total_pagado: number | string
  viable: boolean
}

export interface FlujoMes {
  mes: string
  ingresos: number
  gastos_fijos: number
  gastos_variables: number
  gastos: number
  balance: number
  acumulado: number
}

export interface FlujoCaja {
  meses: FlujoMes[]
  gasto_variable_promedio: number
  total_ingresos: number
  total_gastos: number
  balance_final: number
}

export interface Meta {
  id: string
  nombre: string
  monto_objetivo: number | string
  moneda: string
  monto_actual: number
  restante: number
  porcentaje: number
  fecha_limite: string | null
  aporte_mensual_sugerido: number | null
  completada: boolean
  notas: string | null
}

export interface Notificaciones {
  id: string
  canal: 'telegram' | 'email' | 'ambos'
  telegram_chat_id: string | null
  email: string | null
  dias_anticipacion: number
  activo: boolean
  ultima_notificacion: string | null
}

export interface ChatTelegram {
  chat_id: string
  nombre: string
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
