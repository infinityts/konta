interface AccordionLoaderProps {
  /** Se colorea con `currentColor`: usa clases tipo `text-[#2563eb]`. */
  className?: string
  /** Número de barras del acordeón. */
  bars?: number
  /** Texto accesible para lectores de pantalla. */
  label?: string
}

/**
 * Loader «accordion»: barras verticales que se estiran y encogen en secuencia.
 *
 * El color lo hereda del texto, así que basta con `className="text-indigo-600"`.
 */
export function AccordionLoader({
  className = '',
  bars = 5,
  label = 'Cargando',
}: AccordionLoaderProps) {
  return (
    <div
      role="status"
      aria-label={label}
      className={`flex h-10 items-end gap-1 ${className}`}
    >
      {Array.from({ length: bars }).map((_, i) => (
        <span
          key={i}
          className="konta-accordion-bar w-1.5 rounded-full bg-current"
          style={{ animationDelay: `${i * 0.12}s` }}
        />
      ))}
    </div>
  )
}
