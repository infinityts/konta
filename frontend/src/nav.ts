/**
 * Mapa de navegación de Konta.
 *
 * El menú se organiza en **grupos** para no tener 18 opciones sueltas.
 * Jerarquía: `Resumen` (enlace directo) + 5 grupos con submenú.
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

/** Enlace directo, sin submenú. */
export const RESUMEN: ItemNav = { to: '/', label: 'Resumen', icono: '📊' }

export const GRUPOS: GrupoNav[] = [
  {
    id: 'movimientos',
    label: 'Movimientos',
    items: [
      { to: '/transacciones', label: 'Transacciones', icono: '💸' },
      { to: '/cuentas', label: 'Cuentas', icono: '🏦' },
      { to: '/tarjetas', label: 'Tarjetas', icono: '💳' },
      { to: '/suscripciones', label: 'Suscripciones', icono: '🔁' },
      { to: '/polizas', label: 'Seguros', icono: '🛡️' },
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
      { to: '/facturas', label: 'Facturas', icono: '🧾' },
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
