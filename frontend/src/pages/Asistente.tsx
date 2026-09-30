import { useEffect, useRef, useState } from 'react'
import { api } from '../api'
import type { CuotaIa, RespuestaAsistente } from '../types'

/** Una vuelta de la conversación (se guarda solo mientras la página está abierta). */
interface Turno {
  id: number
  pregunta: string
  respuesta?: string
  herramientas?: string[]
  error?: string
}

const NOMBRE_HERRAMIENTA: Record<string, string> = {
  resumen: 'tu resumen del mes',
  movimientos: 'tus movimientos',
  gastos_por_categoria: 'tus gastos por categoría',
  evolucion: 'tu evolución de meses',
  cuentas: 'tus cuentas',
  tarjetas: 'tus tarjetas',
  presupuestos: 'tus presupuestos',
  facturas: 'tus facturas',
  mi_plan: 'tu plan',
  ayuda: 'la ayuda de la app',
}

/**
 * El asistente: responde con las reglas de Konta.
 *
 * No calcula nada: pide los datos por herramientas que leen **tus** cuentas con tu sesión, y
 * cada respuesta dice qué consultó. Es de solo lectura: no registra ni cambia nada.
 */
export default function Asistente() {
  const [pregunta, setPregunta] = useState('')
  const [turnos, setTurnos] = useState<Turno[]>([])
  const [sugerencias, setSugerencias] = useState<string[]>([])
  const [cuota, setCuota] = useState<CuotaIa | null>(null)
  const [pensando, setPensando] = useState(false)
  const finDelHilo = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    void api<{ sugerencias: string[] }>('/asistente/sugerencias')
      .then((r) => setSugerencias(r.sugerencias))
      .catch(() => setSugerencias([]))
    void api<CuotaIa>('/ia/cuota')
      .then(setCuota)
      .catch(() => setCuota(null))
  }, [])

  useEffect(() => {
    finDelHilo.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [turnos, pensando])

  async function preguntar(texto: string) {
    const limpia = texto.trim()
    if (limpia.length < 3 || pensando) return
    const id = Date.now()
    setPregunta('')
    setTurnos((t) => [...t, { id, pregunta: limpia }])
    setPensando(true)
    try {
      const r = await api<RespuestaAsistente>('/asistente/preguntar', {
        method: 'POST',
        body: JSON.stringify({ pregunta: limpia }),
      })
      setTurnos((t) =>
        t.map((x) =>
          x.id === id ? { ...x, respuesta: r.respuesta, herramientas: r.herramientas_usadas } : x,
        ),
      )
    } catch (error) {
      // El mensaje del servidor explica qué pasó (cupo agotado, sin configurar…)
      const mensaje = error instanceof Error ? error.message : 'No pude responder'
      setTurnos((t) => t.map((x) => (x.id === id ? { ...x, error: mensaje } : x)))
    } finally {
      setPensando(false)
      // El contador se refresca pase lo que pase (también cuando se agotó)
      try {
        setCuota(await api<CuotaIa>('/ia/cuota'))
      } catch {
        /* si falla, se queda el contador que ya había */
      }
    }
  }

  const restantes = cuota?.consultas_restantes ?? null

  return (
    <div className="flex h-full max-w-3xl flex-col">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-xl font-semibold">Asistente</h2>
        {restantes !== null && (
          <p className={`text-sm ${restantes > 0 ? 'text-slate-500' : 'text-amber-700'}`}>
            {restantes > 0
              ? `Te quedan ${restantes} de ${cuota?.consultas_incluidas} consultas este mes`
              : 'Sin consultas este mes: puedes subir de plan'}
          </p>
        )}
      </div>
      <p className="mt-1 text-sm text-slate-500">
        Pregúntale lo que quieras sobre la app o sobre tus finanzas. Consulta <strong>tus</strong>{' '}
        datos reales y te dice de dónde sale cada cifra; no cambia nada, solo responde. Cada
        consulta cuenta en tu plan.
      </p>

      <div className="mt-4 flex-1 space-y-3 overflow-y-auto">
        {turnos.length === 0 && (
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <p className="text-sm text-slate-600">Prueba con alguna de estas:</p>
            <div className="mt-2 flex flex-wrap gap-2">
              {sugerencias.map((s) => (
                <button
                  key={s}
                  onClick={() => void preguntar(s)}
                  className="rounded-full border border-indigo-200 bg-indigo-50 px-3 py-1 text-sm text-indigo-700 hover:bg-indigo-100"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {turnos.map((t, i) => (
          <div key={i} className="space-y-2">
            <p className="text-right">
              <span className="inline-block rounded-2xl bg-indigo-600 px-3 py-2 text-sm text-white">
                {t.pregunta}
              </span>
            </p>
            {t.respuesta && (
              <div className="rounded-2xl border border-slate-200 bg-white px-3 py-2">
                <p className="whitespace-pre-wrap text-sm text-slate-700">{t.respuesta}</p>
                <p className="mt-2 text-xs text-slate-400">
                  {t.herramientas?.length
                    ? `Consultó: ${t.herramientas
                        .map((h) => NOMBRE_HERRAMIENTA[h] ?? h)
                        .join(', ')}`
                    : 'Respondió sin consultar tus datos'}
                </p>
              </div>
            )}
            {t.error && (
              <div className="rounded-2xl border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
                {t.error}
              </div>
            )}
          </div>
        ))}

        {pensando && (
          <p className="text-sm text-slate-500">Consultando tus datos… (puede tardar unos segundos)</p>
        )}
        <div ref={finDelHilo} />
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault()
          void preguntar(pregunta)
        }}
        className="mt-4 flex flex-wrap items-center gap-2"
      >
        <input
          value={pregunta}
          onChange={(e) => setPregunta(e.target.value)}
          placeholder="Escribe tu pregunta (ej. ¿cuánto gasté en mercado este mes?)"
          className="min-w-0 flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm"
        />
        <button
          type="submit"
          disabled={pensando || pregunta.trim().length < 3}
          className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
        >
          {pensando ? 'Pensando…' : 'Preguntar'}
        </button>
      </form>
      <p className="mt-2 text-xs text-slate-400">
        Cada pregunta es independiente (no recuerda la anterior). Las respuestas se pueden
        equivocar: si una cifra no cuadra, mírala en su pantalla.
      </p>
    </div>
  )
}
