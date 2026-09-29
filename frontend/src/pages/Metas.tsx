import { useEffect, useState } from 'react'
import { api } from '../api'
import { fmtMoney, type Aporte, type Meta } from '../types'

export default function Metas() {
  const [items, setItems] = useState<Meta[]>([])
  const [form, setForm] = useState({ nombre: '', monto_objetivo: '', fecha_limite: '' })
  const [aportes, setAportes] = useState<Record<string, string>>({})
  const [show, setShow] = useState(false)
  const [error, setError] = useState('')
  // Los aportes de una meta se piden al abrirlos, no con la lista entera
  const [abiertos, setAbiertos] = useState<Record<string, boolean>>({})
  const [listaAportes, setListaAportes] = useState<Record<string, Aporte[]>>({})
  const [ocupado, setOcupado] = useState('')

  async function cargar() {
    try {
      setItems(await api<Meta[]>('/metas'))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Error')
    }
  }

  useEffect(() => {
    cargar()
  }, [])

  async function crear() {
    setError('')
    try {
      await api('/metas', {
        method: 'POST',
        body: JSON.stringify({
          nombre: form.nombre,
          monto_objetivo: form.monto_objetivo,
          fecha_limite: form.fecha_limite || null,
        }),
      })
      setForm({ nombre: '', monto_objetivo: '', fecha_limite: '' })
      setShow(false)
      cargar()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Error al guardar')
    }
  }

  async function aportar(metaId: string) {
    const monto = aportes[metaId]
    if (!monto) return
    await api(`/metas/${metaId}/aportes`, { method: 'POST', body: JSON.stringify({ monto }) })
    setAportes((a) => ({ ...a, [metaId]: '' }))
    cargar()
  }

  async function eliminar(id: string) {
    await api(`/metas/${id}`, { method: 'DELETE' })
    cargar()
  }

  /** Abre o cierra el detalle de aportes de una meta (y los trae la primera vez). */
  async function verAportes(metaId: string) {
    const abierto = !abiertos[metaId]
    setAbiertos((a) => ({ ...a, [metaId]: abierto }))
    if (!abierto || listaAportes[metaId]) return
    setOcupado(metaId)
    try {
      const datos = await api<Aporte[]>(`/metas/${metaId}/aportes`)
      setListaAportes((a) => ({ ...a, [metaId]: datos }))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudieron leer los aportes')
    } finally {
      setOcupado('')
    }
  }

  /**
   * Borra un aporte. El saldo de la meta lo recalcula el backend al quitarlo, así que
   * después se recarga la lista de metas y los aportes de esa meta.
   */
  async function borrarAporte(metaId: string, aporteId: string) {
    if (!confirm('¿Borrar este aporte? El saldo de la meta baja.')) return
    setOcupado(aporteId)
    setError('')
    try {
      await api(`/metas/aportes/${aporteId}`, { method: 'DELETE' })
      const datos = await api<Aporte[]>(`/metas/${metaId}/aportes`)
      setListaAportes((a) => ({ ...a, [metaId]: datos }))
      await cargar()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo borrar el aporte')
    } finally {
      setOcupado('')
    }
  }

  const totalObjetivo = items.reduce((s, m) => s + Number(m.monto_objetivo), 0)
  const totalAhorrado = items.reduce((s, m) => s + m.monto_actual, 0)

  return (
    <div>
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold">Metas de ahorro</h2>
        <button onClick={() => setShow((s) => !s)} className="rounded-lg bg-indigo-600 px-3 py-2 text-sm font-medium text-white hover:bg-indigo-700">
          {show ? 'Cancelar' : 'Nueva meta'}
        </button>
      </div>

      {items.length > 0 && (
        <p className="mt-2 text-sm text-slate-500">
          Ahorrado {fmtMoney(totalAhorrado)} de {fmtMoney(totalObjetivo)} en {items.length} meta(s).
        </p>
      )}

      {show && (
        <div className="mt-4 grid gap-3 rounded-xl border border-slate-200 bg-white p-4 sm:grid-cols-3">
          <input placeholder="Nombre (ej. Viaje)" value={form.nombre} onChange={(e) => setForm((f) => ({ ...f, nombre: e.target.value }))} className="rounded-lg border border-slate-300 px-3 py-2 text-sm" />
          <input placeholder="Monto objetivo" value={form.monto_objetivo} onChange={(e) => setForm((f) => ({ ...f, monto_objetivo: e.target.value }))} className="rounded-lg border border-slate-300 px-3 py-2 text-sm" />
          <input type="date" value={form.fecha_limite} onChange={(e) => setForm((f) => ({ ...f, fecha_limite: e.target.value }))} className="rounded-lg border border-slate-300 px-3 py-2 text-sm" />
          <button onClick={crear} className="rounded-lg bg-indigo-600 px-3 py-2 text-sm text-white hover:bg-indigo-700 sm:col-span-3">Guardar</button>
        </div>
      )}

      {error && <p className="mt-3 text-sm text-red-600">{error}</p>}

      <ul className="mt-4 space-y-3">
        {items.map((m) => (
          <li key={m.id} className="rounded-xl border border-slate-200 bg-white p-4">
            <div className="flex items-center justify-between">
              <div>
                <span className="font-medium">{m.nombre}</span>
                {m.completada && <span className="ml-2 text-sm text-emerald-600">✓ completada</span>}
                {m.fecha_limite && <span className="ml-2 text-xs text-slate-400">límite {m.fecha_limite}</span>}
              </div>
              <button onClick={() => eliminar(m.id)} className="text-sm text-red-600 hover:underline">Eliminar</button>
            </div>

            <div className="mt-2 h-2 w-full rounded-full bg-slate-100">
              <div className={`h-2 rounded-full ${m.completada ? 'bg-emerald-500' : 'bg-indigo-500'}`} style={{ width: `${Math.min(m.porcentaje, 100)}%` }} />
            </div>

            <div className="mt-2 flex flex-wrap items-center justify-between gap-2 text-sm">
              <span className="text-slate-600">
                {fmtMoney(m.monto_actual)} / {fmtMoney(m.monto_objetivo)}
                <span className="ml-2 font-medium text-slate-800">{m.porcentaje}%</span>
                {!m.completada && <span className="ml-2 text-slate-500">· faltan {fmtMoney(m.restante)}</span>}
              </span>
              {m.aporte_mensual_sugerido != null && !m.completada && (
                <span className="text-xs text-indigo-600">💡 ahorra {fmtMoney(m.aporte_mensual_sugerido)}/mes</span>
              )}
            </div>

            <div className="mt-3 flex flex-wrap items-center gap-2">
              <input
                placeholder="Aportar"
                value={aportes[m.id] ?? ''}
                onChange={(e) => setAportes((a) => ({ ...a, [m.id]: e.target.value }))}
                className="w-32 rounded-lg border border-slate-300 px-3 py-2 text-sm"
              />
              <button onClick={() => aportar(m.id)} className="rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-700 hover:bg-slate-50">
                Aportar
              </button>
              <button
                onClick={() => verAportes(m.id)}
                className="rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-700 hover:bg-slate-50"
              >
                {abiertos[m.id] ? 'Ocultar aportes' : 'Ver aportes'}
              </button>
            </div>

            {abiertos[m.id] && (
              <div className="mt-3 rounded-lg border border-slate-200 bg-slate-50 p-3">
                {ocupado === m.id ? (
                  <p className="text-sm text-slate-500">Cargando aportes…</p>
                ) : (listaAportes[m.id]?.length ?? 0) === 0 ? (
                  <p className="text-sm text-slate-500">Todavía no hay aportes en esta meta.</p>
                ) : (
                  <ul className="divide-y divide-slate-200">
                    {listaAportes[m.id].map((a) => (
                      <li key={a.id} className="flex items-center justify-between py-2 text-sm">
                        <span className="text-slate-700">
                          {a.fecha} · <strong>{fmtMoney(a.monto)}</strong>
                          {a.notas && <span className="ml-2 text-slate-500">{a.notas}</span>}
                        </span>
                        <button
                          onClick={() => borrarAporte(m.id, a.id)}
                          disabled={ocupado === a.id}
                          className="text-red-600 hover:underline disabled:opacity-50"
                        >
                          {ocupado === a.id ? 'Borrando…' : 'Borrar'}
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}
          </li>
        ))}
        {items.length === 0 && <p className="text-sm text-slate-500">Aún no tienes metas de ahorro.</p>}
      </ul>
    </div>
  )
}
