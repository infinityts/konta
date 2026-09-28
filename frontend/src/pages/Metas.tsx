import { useEffect, useState } from 'react'
import { api } from '../api'
import { fmtMoney, type Meta } from '../types'

export default function Metas() {
  const [items, setItems] = useState<Meta[]>([])
  const [form, setForm] = useState({ nombre: '', monto_objetivo: '', fecha_limite: '' })
  const [aportes, setAportes] = useState<Record<string, string>>({})
  const [show, setShow] = useState(false)
  const [error, setError] = useState('')

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
            </div>
          </li>
        ))}
        {items.length === 0 && <p className="text-sm text-slate-500">Aún no tienes metas de ahorro.</p>}
      </ul>
    </div>
  )
}
