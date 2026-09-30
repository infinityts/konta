export interface Categoria {
  id: string
  nombre: string
  tipo: 'ingreso' | 'gasto'
  icono: string | null
  color: string | null
}

export interface PagoTarjeta {
  id: string
  tarjeta_id: string
  cuenta_id: string | null
  transaccion_id: string | null
  monto: number | string
  moneda: string
  fecha: string
  notas: string | null
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
  pagos: PagoTarjeta[]
  /** Vigente = extracto − pagos posteriores: lo que se debe hoy */
  deuda_por_moneda: Record<string, number>
  extracto_por_moneda: Record<string, number>
  pagos_por_moneda: Record<string, number>
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
  /** De dónde sale el dinero: sin esto el gasto generado no movía ningún saldo */
  cuenta_id: string | null
  estado: string
  notas: string | null
}

export type TipoTransaccion = 'ingreso' | 'gasto' | 'transferencia'

export interface Transaccion {
  id: string
  tipo: TipoTransaccion
  monto: number | string
  moneda: string
  fecha: string
  descripcion: string | null
  categoria_id: string | null
  tarjeta_id: string | null
  suscripcion_id: string | null
  etiqueta_id: string | null
  cuenta_id: string | null
  /** Solo en una transferencia: la cuenta que recibe */
  cuenta_destino_id?: string | null
  poliza_id?: string | null
  /** Lo rellena el servidor si el movimiento lo generó un compromiso recurrente */
  ingreso_recurrente_id?: string | null
  notas: string | null
}

export interface Movimiento {
  id: string | null
  ids: string[]
  tipo: TipoTransaccion
  monto: number | string
  fecha: string
  descripcion: string | null
  categoria_id: string | null
  categoria: string | null
  etiqueta_id: string | null
  etiquetas: string[]
  factura_id: string | null
  articulos: number
  agrupada: boolean
  cuenta_id: string | null
  cuenta_destino_id: string | null
  tarjeta_id: string | null
  moneda: string
  notas: string | null
  busqueda: string
  suscripcion_id: string | null
  ingreso_recurrente_id: string | null
  poliza_id: string | null
}

export interface ArticuloDetalle {
  id: string
  descripcion: string
  cantidad: number | string | null
  valor_unitario: number | string | null
  valor_total: number | string
  origen: string
}

export interface GrupoDetalle {
  etiqueta: string | null
  categoria: string | null
  total: number | string
  porcentaje: number | string
  articulos: ArticuloDetalle[]
}

export interface DetalleFactura {
  factura_id: string
  descripcion: string | null
  total: number | string
  articulos: number
  grupos: GrupoDetalle[]
}

export interface ReglaOcr {
  id: string
  patron: string
  etiqueta_id: string
  etiqueta_nombre: string | null
  categoria_id: string | null
  categoria_nombre: string | null
  /** Cuántas veces la ha usado el clasificador */
  veces_usada: number
  creada_en: string
  actualizada_en: string
}

export interface CopiarEtiquetas {
  previsualizar: boolean
  creadas: Etiqueta[]
  /** Rutas que ya existían en el destino: no se duplican */
  omitidas: string[]
  /** Rutas que se crearían (solo en la previsualización) */
  plan: string[]
  total_creadas: number
}

export interface Etiqueta {
  id: string
  nombre: string
  color: string | null
  categoria_id: string | null
  padre_id: string | null
}

export interface Alerta {
  tipo: 'suscripcion' | 'tarjeta_pago' | 'tarjeta_corte' | 'poliza_pago' | 'poliza_vencimiento'
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
  transferencias_enviadas?: number
  transferencias_recibidas?: number
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
  impuestos_total: number | string | null
  iva_valor: number | string | null
  descuento: number | string | null
  /** Del QR de la factura electrónica */
  cude: string | null
  url_dian: string | null
  duplicada: boolean
  /** Si el monto detectado no es de fiar: por qué (null = está bien) */
  aviso_monto?: string | null
  /** Lo mismo con la fecha (decide en qué mes cae el gasto) */
  aviso_fecha?: string | null
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
  iva_tipo: 'gravado' | 'exento' | 'excluido' | null
}

export interface FacturaDetalle extends Factura {
  lineas: FacturaLinea[]
  tipo_documento: string | null
  transaccion_monto: number | string | null
  descuadre: number | string | null
  /** Lo que hay que decir de esta lectura (p. ej. «no se duplicaron N líneas») */
  aviso: string | null
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
  /** Todo el flujo viene en esta moneda (COP); el resto se convierte con la tasa. */
  moneda: string
  /** Monedas sin tasa registrada: sus importes no se sumaron. */
  sin_tasa: string[]
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

export interface Aporte {
  id: string
  meta_id: string
  monto: number | string
  fecha: string
  notas: string | null
}

export interface Notificaciones {
  id: string
  canal: 'telegram' | 'email' | 'whatsapp' | 'ambos' | 'todos'
  telegram_chat_id: string | null
  whatsapp_numero: string | null
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
  /** En qué cuenta entra */
  cuenta_id: string | null
  activa: boolean
}

export interface Beneficiario {
  id: string
  usuario_id: string
  poliza_id: string
  nombre: string
  parentesco: string | null
  porcentaje: number | string | null
}

/** Persona cubierta por la póliza (una póliza familiar cubre a varias). */
export interface Asegurado {
  id: string
  usuario_id: string
  poliza_id: string
  nombre: string
  parentesco: string | null
  fecha_nacimiento: string | null
  es_titular: boolean
}

export type TipoPoliza = 'vida' | 'salud' | 'vehiculo' | 'hogar' | 'otro'

export interface Poliza {
  id: string
  usuario_id: string
  tipo: TipoPoliza
  aseguradora: string
  numero_poliza: string | null
  asegurado_nombre: string | null
  placa: string | null
  marca: string | null
  modelo: string | null
  anio: number | null
  valor_asegurado: number | string | null
  prima: number | string
  moneda: string
  periodicidad: 'semanal' | 'mensual' | 'trimestral' | 'semestral' | 'anual'
  fecha_inicio: string | null
  fecha_fin: string | null
  proximo_pago: string | null
  renovacion_automatica: boolean
  categoria_id: string | null
  etiqueta_id: string | null
  tarjeta_id: string | null
  cuenta_id: string | null
  estado: 'activa' | 'pausada' | 'cancelada'
  notas: string | null
  creada_en: string
  beneficiarios: Beneficiario[]
  asegurados: Asegurado[]
  prima_mensual_cop: number | null
  titulo: string
}

export interface PolizaPorTipo {
  tipo: string
  polizas: number
  prima_mensual_cop: number
  prima_anual_cop: number
}

export interface PolizaResumen {
  polizas_activas: number
  prima_mensual_cop: number
  prima_anual_cop: number
  sin_tasa: string[]
  por_tipo: PolizaPorTipo[]
}

export function fmtMoney(v: number | string | null | undefined): string {
  const n = Number(v)
  if (!Number.isFinite(n)) return '—'
  return `$${n.toLocaleString('es-CO', { minimumFractionDigits: 0, maximumFractionDigits: 2 })}`
}

// ---------------------------------------------------------------------------
// Extractos bancarios (Fase 1: ingesta y análisis)
// ---------------------------------------------------------------------------

export interface ExtractoMovimiento {
  id: string
  orden: number
  fecha: string | null
  descripcion: string
  valor: string
  moneda: string
  saldo: string | null
  monto_original: string | null
  moneda_original: string | null
  tasa_cambio: string | null
  cuotas_n: number | null
  cuotas_total: number | null
  cuota_mes: string | null
  valor_pendiente: string | null
  titular: string | null
  tipo: string
  categoria_id: string | null
  etiqueta_id: string | null
  origen: string
  es_informativo: boolean
  transaccion_id: string | null
}

export interface ControlConciliacion {
  nombre: string
  calculado: string | null
  declarado: string | null
  diferencia?: string
  ok: boolean | null
  filas_dudosas?: Array<Record<string, string>>
}

export interface Extracto {
  id: string
  tipo: string
  formato: string
  banco: string | null
  nombre_archivo: string
  moneda: string
  cuenta_id: string | null
  tarjeta_id: string | null
  periodo_desde: string | null
  periodo_hasta: string | null
  fecha_corte: string | null
  fecha_pago: string | null
  compras: string | null
  abonos: string | null
  intereses: string | null
  otros_cargos: string | null
  pago_total: string | null
  pago_minimo: string | null
  cupo_total: string | null
  cupo_disponible: string | null
  conciliacion_ok: boolean
  creado_en: string
}

export interface ExtractoDetalle extends Extracto {
  saldo_anterior: string | null
  intereses_mora: string | null
  movimientos: ExtractoMovimiento[]
  conciliacion: ControlConciliacion[]
}

export interface TramoCategoria {
  categoria: string
  total: string
  etiquetas: string[]
}

export interface AnalisisExtracto {
  extracto_id: string
  moneda: string
  moneda_extracto: string
  moneda_solicitada: string
  conversion_aplicada: boolean
  conciliacion_ok: boolean
  conciliacion: ControlConciliacion[]
  compras: string
  pagos: string
  intereses: string
  comisiones: string
  costos_financieros: string
  movimientos: number
  movimientos_informativos: number
  por_moneda: Record<string, Record<string, number | string>>
  por_categoria: TramoCategoria[]
  compromiso_futuro: Record<string, string>
  cupo_total: string | null
  cupo_disponible: string | null
  cupo_utilizado: string | null
  pago_total: string | null
  pago_minimo: string | null
  intereses_declarados: string | null
  avisos: string[]
  sin_tasa: Array<Record<string, string>>
}

export interface ImportarLinea {
  /** Nulo si la línea la declara el corte (intereses, comisiones) y no es un movimiento */
  movimiento_id: string | null
  fecha: string | null
  descripcion: string
  moneda: string
  monto: string
  valor_compra: string
  tipo: string
  incluir: boolean
  motivo: string | null
  ya_importado: boolean
  es_gasto: boolean
}

export interface ImportarPreview {
  extracto_id: string
  lineas: ImportarLinea[]
  resumen: ImportarResumen
  pago_minimo: string | null
  diferencia_pago_minimo: string | null
  nota_pago_minimo: string | null
}

export interface ImportarResumen {
  total: number
  se_importan: number
  se_omiten: number
  gastos_por_moneda: Record<string, string>
  ingresos_por_moneda: Record<string, string>
  motivos: Record<string, number>
  de_meses_anteriores: string
}

export interface ImportarResultado extends ImportarResumen {
  extracto_id: string
  creadas: number
  deuda_registrada: string | null
  pago_minimo: string | null
  diferencia_pago_minimo: string | null
  nota_pago_minimo: string | null
}

export interface CandidatoRecurrente {
  clave: string
  nombre: string
  descripcion: string
  monto: string
  moneda: string
  periodicidad: string
  ultima_fecha: string | null
  proximo_pago: string | null
  apariciones: number
  fechas: string[]
  montos: string[]
  confianza: 'alta' | 'media' | 'baja'
  senales: string[]
  ya_es_suscripcion: boolean
  categoria_id: string | null
  etiqueta_id: string | null
  en_este_extracto: boolean
}

export interface CrearRecurrentesResultado {
  creadas: Suscripcion[]
  omitidas: string[]
}

export interface CompraCuotas {
  descripcion: string
  moneda: string
  valor_compra: string
  cuota_mes: string
  cuotas: string
  cuotas_restantes: number
  pendiente: string
  tasa_ea: string | null
}

export interface Proyeccion {
  desde: string
  meses: string[]
  por_moneda: Record<
    string,
    {
      pendiente: string
      cuota_mensual_actual: string
      compras: number
      meses: Record<string, string>
    }
  >
  detalle: CompraCuotas[]
}

export interface CostoExtracto {
  extracto_id: string
  banco: string | null
  nombre_archivo: string
  moneda: string
  fecha_corte: string | null
  intereses: string
  comisiones: string
  costo: string
  pago_minimo: string | null
  porcentaje_del_pago: number | null
}

export interface CostosDelDinero {
  extractos: CostoExtracto[]
  total_por_moneda: Record<string, string>
}

export interface Hallazgo {
  nombre: string
  ok: boolean | null
  detalle: string
  sugerencia: string | null
}

export interface SimulacionExtracto {
  moneda: string
  saldo: string
  pago_mensual: string
  tasa_ea: string | null
  tasa_mensual: string | null
  fuente_de_la_tasa: string | null
  cuota_actual: string | null
  meses: number | null
  total_intereses: string | null
  total_pagado: string | null
  viable: boolean | null
  aviso: string | null
}

export interface PanelKpis {
  ingresos: number
  gastos: number
  balance: number
  iva: number
  compras: number
}

export interface PanelSerie {
  mes: string
  ingresos: number
  gastos: number
  balance: number
  iva: number
  compras: number
}

export interface PanelCategoria {
  categoria: string
  total: number
  anterior: number
  variacion: number
}

export interface PanelEtiqueta {
  etiqueta: string
  total: number
  anterior: number
  variacion: number
}

export interface PanelProducto {
  descripcion: string
  total: number
  veces: number
  precio_promedio: number | null
}

export interface PanelReporte {
  mes: string
  anterior: string
  kpis: PanelKpis
  serie: PanelSerie[]
  categorias: PanelCategoria[]
  mercado: { etiquetas: PanelEtiqueta[]; productos: PanelProducto[] }
  impuestos: { mes: number; periodo: number; sobre_compras: number | null }
}

/** Lo que el lector ha aprendido de un emisor: dónde viene el total y la fecha. */
export interface PlantillaLector {
  id: string
  emisor: string
  nombre: string
  campo_monto: string | null
  campo_fecha: string | null
  tipo_documento: string | null
  usos: number
  actualizada_en: string
}

/** Un renglón que el usuario borra siempre: no es un artículo. */
export interface PatronIgnorado {
  id: string
  patron: string
  ejemplo: string
  veces: number
  actualizada_en: string
}
