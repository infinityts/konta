/**
 * Mapa de navegación de Konta.
 *
 * El menú se organiza en **grupos** para no tener 18 opciones sueltas.
 * Jerarquía: `Resumen` (enlace directo) + 6 grupos con submenú.
 *
 * Los **recurrentes** (gastos e ingresos) tienen su propio grupo: son el mismo
 * concepto —«esto se repite solo»— y tenerlos separados con nombres distintos
 * («Suscripciones») hacía que un arriendo o un colegio no se reconocieran como lo
 * que son.
 */

export interface ItemNav {
  to: string
  label: string
  icono: string
}

export interface GrupoNav {
  id: string
  label: string
  items: ItemNav[]
}

/**
 * Enlace directo, sin submenú.
 */
export const RESUMEN: ItemNav = { to: '/', label: 'Resumen', icono: '📊' }

export const GRUPOS: GrupoNav[] = [
  {
    id: 'movimientos',
    label: 'Movimientos',
    items: [
      { to: '/transacciones', label: 'Transacciones', icono: '💸' },
      { to: '/cuentas', label: 'Cuentas', icono: '🏦' },
      { to: '/tarjetas', label: 'Tarjetas', icono: '💳' },
      { to: '/polizas', label: 'Seguros', icono: '🛡️' },
    ],
  },
  {
    id: 'recurrentes',
    label: 'Recurrentes',
    items: [
      // «Gastos recurrentes» es la ruta /suscripciones de siempre: arriendo, colegio,
      // servicios, streaming… todo lo que se repite solo.
      { to: '/suscripciones', label: 'Gastos recurrentes', icono: '🔁' },
      { to: '/ingresos-recurrentes', label: 'Ingresos recurrentes', icono: '📅' },
    ],
  },
  {
    id: 'analisis',
    label: 'Análisis',
    items: [
      { to: '/reportes', label: 'Reportes', icono: '📈' },
      { to: '/flujo', label: 'Flujo de caja', icono: '🌊' },
      { to: '/presupuestos', label: 'Presupuestos', icono: '🎯' },
      { to: '/metas', label: 'Metas', icono: '🐖' },
    ],
  },
  {
    id: 'organizacion',
    label: 'Organización',
    items: [
      { to: '/categorias', label: 'Categorías', icono: '🗂️' },
      { to: '/etiquetas', label: 'Etiquetas', icono: '🏷️' },
    ],
  },
  {
    id: 'herramientas',
    label: 'Herramientas',
    items: [
      { to: '/extractos', label: 'Extractos', icono: '📄' },
      { to: '/deuda-cuotas', label: 'Deuda y cuotas', icono: '📉' },
      { to: '/facturas', label: 'Facturas', icono: '🧾' },
      { to: '/reglas-ocr', label: 'Reglas de OCR', icono: '🧠' },
      { to: '/importar', label: 'Importar', icono: '📥' },
      { to: '/mercado', label: 'Mercado', icono: '🛒' },
    ],
  },
  {
    id: 'configuracion',
    label: 'Configuración',
    items: [
      { to: '/monedas', label: 'Monedas', icono: '💱' },
      { to: '/notificaciones', label: 'Notificaciones', icono: '🔔' },
      { to: '/respaldo', label: 'Respaldo', icono: '💾' },
    ],
  },
]

/** Grupo al que pertenece una ruta (para resaltar el menú). */
export function grupoDeRuta(pathname: string): string | null {
  const grupo = GRUPOS.find((g) => g.items.some((i) => i.to === pathname))
  return grupo?.id ?? null
}
