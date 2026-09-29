import { useEffect, useMemo, useRef, useState, type KeyboardEvent as TeclaReact } from 'react'

/**
 * Desplegable con **búsqueda** para listas largas de etiquetas.
 *
 * Un `<select>` con 40 etiquetas es incómodo: hay que recorrerlas con el ojo. Aquí se
 * escribe y filtra al instante, buscando tanto por el nombre como por la categoría, y
 * sin importar acentos ni mayúsculas.
 *
 * Sin dependencias nuevas: es un `<input>` con una lista.
 */

export interface Opcion {
  id: string
  label: string
  /** La categoría, para agrupar visualmente y poder buscar por ella. */
  grupo?: string
}

/** Sin acentos y en minúsculas, para que «lacteos» encuentre «Lácteos». */
export function normalizarBusqueda(texto: string): string {
  return texto
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .trim()
}

/**
 * Filtra por nombre **y** por categoría. Es una función pura: se puede probar sola.
 *
 * Busca en cualquier parte del texto (no solo al principio) porque uno escribe «yogur»
 * esperando encontrar `Lácteos y huevos › Yogur`.
 */
export function filtrarOpciones(opciones: Opcion[], consulta: string): Opcion[] {
  const q = normalizarBusqueda(consulta)
  if (!q) return opciones
  return opciones.filter((o) => normalizarBusqueda(`${o.grupo ?? ''} ${o.label}`).includes(q))
}

interface Props {
  opciones: Opcion[]
  value: string
  onChange: (id: string) => void
  /** Texto del buscador al abrir. */
  placeholder?: string
  /** Opción para dejar la línea sin etiqueta. Vacío = no mostrar esa opción. */
  textoVacio?: string
  disabled?: boolean
  className?: string
}

export default function SelectBuscable({
  opciones,
  value,
  onChange,
  placeholder = 'Buscar etiqueta…',
  textoVacio = 'Sin etiqueta',
  disabled = false,
  className,
}: Props) {
  const [abierto, setAbierto] = useState(false)
  const [consulta, setConsulta] = useState('')
  const [resaltado, setResaltado] = useState(0)
  const contenedor = useRef<HTMLDivElement>(null)
  const entrada = useRef<HTMLInputElement>(null)

  const seleccionada = opciones.find((o) => o.id === value)
  const filtradas = useMemo(() => filtrarOpciones(opciones, consulta), [opciones, consulta])

  // Cerrar al hacer clic fuera
  useEffect(() => {
    if (!abierto) return
    function alClicFuera(evento: MouseEvent) {
      if (contenedor.current && !contenedor.current.contains(evento.target as Node)) {
        setAbierto(false)
      }
    }
    document.addEventListener('mousedown', alClicFuera)
    return () => document.removeEventListener('mousedown', alClicFuera)
  }, [abierto])

  // El cursor empieza en el buscador al abrir
  useEffect(() => {
    if (abierto) entrada.current?.focus()
  }, [abierto])

  function elegir(id: string) {
    onChange(id)
    setAbierto(false)
    setConsulta('')
  }

  function alTeclear(evento: TeclaReact<HTMLInputElement>) {
    if (evento.key === 'ArrowDown') {
      evento.preventDefault()
      setResaltado((i) => Math.min(i + 1, Math.max(filtradas.length - 1, 0)))
    } else if (evento.key === 'ArrowUp') {
      evento.preventDefault()
      setResaltado((i) => Math.max(i - 1, 0))
    } else if (evento.key === 'Enter') {
      evento.preventDefault()
      const opcion = filtradas[resaltado]
      if (opcion) elegir(opcion.id)
      else if (textoVacio) elegir('')
    } else if (evento.key === 'Escape') {
      setAbierto(false)
      setConsulta('')
    }
  }

  return (
    <div ref={contenedor} className={`relative ${className ?? ''}`}>
      <button
        type="button"
        disabled={disabled}
        onClick={() => setAbierto((a) => !a)}
        className="flex w-full items-center justify-between gap-1 rounded-lg border border-slate-300 px-2 py-1 text-left text-sm disabled:bg-slate-100 disabled:text-slate-500"
      >
        <span className={seleccionada ? 'text-slate-700' : 'text-slate-400'}>
          {seleccionada ? seleccionada.label : textoVacio || '—'}
        </span>
        <span className="text-xs text-slate-400">▾</span>
      </button>

      {abierto && (
        <div className="absolute z-20 mt-1 w-72 rounded-lg border border-slate-300 bg-white shadow-lg">
          <input
            ref={entrada}
            value={consulta}
            onChange={(e) => {
              setConsulta(e.target.value)
              setResaltado(0)
            }}
            onKeyDown={alTeclear}
            placeholder={placeholder}
            className="w-full rounded-t-lg border-b border-slate-200 px-2 py-1.5 text-sm outline-none"
          />
          <ul className="max-h-56 overflow-auto py-1">
            {textoVacio && (
              <li>
                <button
                  type="button"
                  onClick={() => elegir('')}
                  className="block w-full px-3 py-1 text-left text-xs text-slate-500 hover:bg-slate-50"
                >
                  {textoVacio}
                </button>
              </li>
            )}
            {filtradas.length === 0 && (
              <li className="px-3 py-2 text-xs text-slate-400">
                Nada coincide con «{consulta}»
              </li>
            )}
            {filtradas.map((opcion, i) => (
              <li key={opcion.id}>
                <button
                  type="button"
                  onMouseEnter={() => setResaltado(i)}
                  onClick={() => elegir(opcion.id)}
                  className={`flex w-full items-baseline justify-between gap-2 px-3 py-1 text-left text-sm ${
                    i === resaltado ? 'bg-indigo-50' : ''
                  } ${opcion.id === value ? 'font-medium text-indigo-700' : 'text-slate-700'}`}
                >
                  <span>{opcion.label}</span>
                  {opcion.grupo && (
                    <span className="shrink-0 text-[11px] text-slate-400">{opcion.grupo}</span>
                  )}
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
