/**
 * La marca de Konta: la K del icono, sin el cuadro de fondo.
 *
 * Va en línea (no como imagen) para que herede el tamaño del texto y no cueste una petición.
 * Los colores son los del icono: la K en índigo y el brazo de arriba en esmeralda — el trazo
 * que sube. Se usa sobre blanco, que es el fondo de la app.
 */
export function KIcono({ className = '' }: { className?: string }) {
  return (
    <svg
      viewBox="197 136 709 752"
      className={className}
      role="img"
      aria-label="Konta"
      fill="none"
    >
      <path d="M307 246V778" stroke="#4f46e5" strokeWidth="220" strokeLinecap="round" />
      <path d="M339 512 796 246" stroke="#10b981" strokeWidth="220" strokeLinecap="round" />
      <path d="M339 512 796 778" stroke="#4f46e5" strokeWidth="220" strokeLinecap="round" />
    </svg>
  )
}

/** La K y el nombre juntos (para cabeceras). */
export default function Marca({ className = '', alto = 'h-7' }: { className?: string; alto?: string }) {
  return (
    <span className={`flex items-center gap-2 ${className}`}>
      <KIcono className={`${alto} w-auto`} />
      <span className="text-lg font-bold tracking-tight text-slate-900">
        Kon<span className="text-indigo-600">ta</span>
      </span>
    </span>
  )
}
