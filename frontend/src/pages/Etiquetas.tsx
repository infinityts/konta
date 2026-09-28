import { useEffect, useState } from 'react'
import { api } from '../api'
import type { Categoria, Etiqueta } from '../types'

export default function Etiquetas() {
  const [etiquetas, setEtiquetas] = useState<Etiqueta[]>([])
  const [categorias, setCategorias] = useState<Categoria[]>([])
  const [form, setForm] = useState({ nombre: '', categoria_id: '', padre_id: '' })
  const [show, setShow] = useState(false)
  const [error, setError] = useState('')

  async function cargar() {
    try {
      setEtiquetas(await api<Etiqueta[]>('/etiquetas'))
      setCategorias(await api<Categoria[]>('/categorias'))
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
          categoria_id: form.padre_id ? null : form.categoria_id || null,
          padre_id: form.padre_id || null,
        }),
      })
      setForm({ nombre: '', categoria_id: form.categoria_id, padre_id: '' })
      cargar()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Error al guardar')
    }
  }

  async function eliminar(id: string) {
    await api(`/etiquetas/${id}`, { method: 'DELETE' })
    cargar()
  }

  const catRaices = categorias.filter((c) => !c.padre_id)
  const subcatsDe = (id: string) => categorias.filter((c) => c.padre_id === id)
  const raicesDe = (catId: string) => etiquetas.filter((e) => e.categoria_id === catId && !e.padre_id)
  const hijasDe = (etqId: string) => etiquetas.filter((e) => e.padre_id === etqId)
  const sinCategoria = etiquetas.filter((e) => !e.categoria_id && !e.padre_id)
  const etqPadresDelForm = etiquetas.filter((e) => e.categoria_id === form.categoria_id && !e.padre_id)

  return (
    <div>
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold">Etiquetas y subetiquetas</h2>
        <button onClick={() => setShow((s) => !s)} className="rounded-lg bg-indigo-600 px-3 py-2 text-sm font-medium text-white hover:bg-indigo-700">
          {show ? 'Cancelar' : 'Nueva etiqueta'}
        </button>
      </div>

      <p className="mt-1 text-sm text-slate-500">
        Las etiquetas viven <strong>dentro de una categoría</strong>:
        <code className="mx-1 rounded bg-slate-100 px-1">Categoría › Etiqueta › Subetiqueta</code>.
        No se permiten dos <strong>hermanas</strong> con el mismo nombre (sin distinguir mayúsculas);
        en categorías distintas sí puedes repetir el nombre.
      </p>
      {error && <p className="mt-2 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}

      {show && (
        <div className="mt-4 grid gap-3 rounded-xl border border-slate-200 bg-white p-4 sm:grid-cols-3">
          <select value={form.categoria_id} onChange={(e) => setForm((f) => ({ ...f, categoria_id: e.target.value, padre_id: '' }))} className="rounded-lg border border-slate-300 px-3 py-2 text-sm">
            <option value="">1) Elige la categoría…</option>
            {catRaices.map((r) => (
              <optgroup key={r.id} label={r.nombre}>
                <option value={r.id}>{r.nombre}</option>
                {subcatsDe(r.id).map((h) => <option key={h.id} value={h.id}>— {h.nombre}</option>)}
              </optgroup>
            ))}
          </select>
          <select
            value={form.padre_id}
            onChange={(e) => setForm((f) => ({ ...f, padre_id: e.target.value }))}
            disabled={!form.categoria_id}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm disabled:bg-slate-100 disabled:text-slate-400"
          >
            <option value="">2) Es una etiqueta</option>
            {etqPadresDelForm.map((e) => <option key={e.id} value={e.id}>Subetiqueta de {e.nombre}</option>)}
          </select>
          <input placeholder="3) Nombre" value={form.nombre} onChange={(e) => setForm((f) => ({ ...f, nombre: e.target.value }))} className="rounded-lg border border-slate-300 px-3 py-2 text-sm" />
          <button
            onClick={crear}
            disabled={!form.categoria_id || !form.nombre}
            className="rounded-lg bg-indigo-600 px-3 py-2 text-sm text-white hover:bg-indigo-700 disabled:bg-slate-300 sm:col-span-3"
          >
            Crear
          </button>
        </div>
      )}

      {sinCategoria.length > 0 && (
        <div className="mt-4 rounded-xl border border-amber-200 bg-amber-50 p-4">
          <p className="text-sm font-medium text-amber-800">Etiquetas sin categoría</p>
          <p className="mt-1 text-xs text-amber-700">
            Son de antes de este cambio. Edítalas (o créalas de nuevo) dentro de una categoría.
          </p>
          <ul className="mt-2 space-y-1">
            {sinCategoria.map((e) => (
              <li key={e.id} className="flex items-center justify-between text-sm text-amber-900">
                <span>{e.nombre}</span>
                <button onClick={() => eliminar(e.id)} className="text-xs text-red-600 hover:underline">quitar</button>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="mt-4 grid gap-4 sm:grid-cols-2">
        {catRaices.map((c) => {
          const etqs = raicesDe(c.id)
          return (
            <div key={c.id} className="rounded-xl border border-slate-200 bg-white p-4">
              <h3 className="font-medium text-slate-800">{c.nombre}</h3>
              {etqs.length === 0 ? (
                <p className="mt-2 text-xs text-slate-400">Sin etiquetas</p>
              ) : (
                <ul className="mt-2 space-y-2">
                  {etqs.map((e) => (
                    <li key={e.id}>
                      <div className="flex items-center justify-between text-sm">
                        <span className="text-slate-700">{e.nombre}</span>
                        <button onClick={() => eliminar(e.id)} className="text-xs text-red-500 hover:underline">quitar</button>
                      </div>
                      {hijasDe(e.id).length > 0 && (
                        <ul className="mt-0.5 space-y-0.5 pl-4">
                          {hijasDe(e.id).map((s) => (
                            <li key={s.id} className="flex items-center justify-between text-xs text-slate-500">
                              <span>↳ {s.nombre}</span>
                              <button onClick={() => eliminar(s.id)} className="text-red-400 hover:underline">quitar</button>
                            </li>
                          ))}
                        </ul>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
