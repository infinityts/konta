import { useEffect, useState } from 'react'
import { api } from '../api'
import type { Etiqueta } from '../types'

const empty = { nombre: '', color: '#6366f1', padre_id: '' }

export default function Etiquetas() {
  const [items, setItems] = useState<Etiqueta[]>([])
  const [form, setForm] = useState(empty)
  const [show, setShow] = useState(false)
  const [error, setError] = useState('')

  async function cargar() {
    try {
      setItems(await api<Etiqueta[]>('/etiquetas'))
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
      await api('/etiquetas', {
        method: 'POST',
        body: JSON.stringify({
          nombre: form.nombre,
          color: form.color || null,
          padre_id: form.padre_id || null,
        }),
      })
      setForm(empty)
      cargar()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Error al guardar')
    }
  }

  async function eliminar(id: string) {
    await api(`/etiquetas/${id}`, { method: 'DELETE' })
    cargar()
  }

  const set = (k: keyof typeof empty, v: string) => setForm((f) => ({ ...f, [k]: v }))
  const raices = items.filter((e) => !e.padre_id)
  const hijasDe = (id: string) => items.filter((e) => e.padre_id === id)

  return (
    <div>
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold">Etiquetas</h2>
        <button onClick={() => setShow((s) => !s)} className="rounded-lg bg-indigo-600 px-3 py-2 text-sm font-medium text-white hover:bg-indigo-700">
          {show ? 'Cancelar' : 'Nueva etiqueta'}
        </button>
      </div>

      {show && (
        <div className="mt-4 grid gap-3 rounded-xl border border-slate-200 bg-white p-4 sm:grid-cols-3">
          <input placeholder="Nombre (ej. Trabajo, Viaje)" value={form.nombre} onChange={(e) => set('nombre', e.target.value)} className="rounded-lg border border-slate-300 px-3 py-2 text-sm" />
          <select value={form.padre_id} onChange={(e) => set('padre_id', e.target.value)} className="rounded-lg border border-slate-300 px-3 py-2 text-sm">
            <option value="">Es etiqueta (raíz)</option>
            {raices.map((r) => (
              <option key={r.id} value={r.id}>Subetiqueta de: {r.nombre}</option>
            ))}
          </select>
          <input type="color" value={form.color} onChange={(e) => set('color', e.target.value)} className="h-10 w-full rounded-lg border border-slate-300" />
          <button onClick={crear} className="rounded-lg bg-indigo-600 px-3 py-2 text-sm text-white hover:bg-indigo-700 sm:col-span-3">Guardar</button>
        </div>
      )}

      {error && <p className="mt-3 text-sm text-red-600">{error}</p>}

      <ul className="mt-4 space-y-2">
        {raices.map((r) => (
          <li key={r.id} className="rounded-xl border border-slate-200 bg-white p-4">
            <div className="flex items-center justify-between">
              <span className="flex items-center gap-2 font-medium">
                <span className="inline-block h-3 w-3 rounded-full" style={{ backgroundColor: r.color ?? '#6366f1' }} />
                {r.nombre}
              </span>
              <button onClick={() => eliminar(r.id)} className="text-sm text-red-600 hover:underline">Eliminar</button>
            </div>
            {hijasDe(r.id).length > 0 && (
              <ul className="mt-2 space-y-1 border-l-2 border-slate-100 pl-4">
                {hijasDe(r.id).map((h) => (
                  <li key={h.id} className="flex items-center justify-between text-sm">
                    <span className="flex items-center gap-2 text-slate-600">
                      <span className="inline-block h-2 w-2 rounded-full" style={{ backgroundColor: h.color ?? '#94a3b8' }} />
                      {h.nombre}
                    </span>
                    <button onClick={() => eliminar(h.id)} className="text-red-600 hover:underline">Eliminar</button>
                  </li>
                ))}
              </ul>
            )}
          </li>
        ))}
        {raices.length === 0 && <p className="text-sm text-slate-500">Aún no tienes etiquetas.</p>}
      </ul>
    </div>
  )
}
