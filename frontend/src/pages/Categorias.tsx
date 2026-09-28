import { useEffect, useState } from 'react'
import { api } from '../api'
import type { Categoria } from '../types'

export default function Categorias() {
  const [items, setItems] = useState<Categoria[]>([])
  const [form, setForm] = useState({ nombre: '', tipo: 'gasto', padre_id: '' })
  const [show, setShow] = useState(false)
  const [error, setError] = useState('')

  async function cargar() {
    try {
      setItems(await api<Categoria[]>('/categorias'))
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
      await api('/categorias', {
        method: 'POST',
        body: JSON.stringify({
          nombre: form.nombre,
          tipo: form.tipo,
          padre_id: form.padre_id || null,
        }),
      })
      setForm({ nombre: '', tipo: form.tipo, padre_id: '' })
      cargar()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Error al guardar')
    }
  }

  async function eliminar(id: string) {
    await api(`/categorias/${id}`, { method: 'DELETE' })
    cargar()
  }

  const raices = items.filter((c) => !c.padre_id)
  const hijasDe = (id: string) => items.filter((c) => c.padre_id === id)
  const padresGasto = items.filter((c) => !c.padre_id && c.tipo === form.tipo)

  const seccion = (tipo: 'gasto' | 'ingreso') => {
    const roots = raices.filter((c) => c.tipo === tipo)
    return (
      <div>
        <h3 className={`font-medium ${tipo === 'gasto' ? 'text-red-600' : 'text-emerald-600'}`}>
          {tipo === 'gasto' ? 'Gastos' : 'Ingresos'}
        </h3>
        <ul className="mt-2 space-y-1">
          {roots.map((c) => (
            <li key={c.id} className="rounded-lg border border-slate-200 bg-white p-3">
              <div className="flex items-center justify-between text-sm">
                <span className="font-medium text-slate-800">{c.nombre}</span>
                <button onClick={() => eliminar(c.id)} className="text-red-600 hover:underline">Eliminar</button>
              </div>
              {hijasDe(c.id).length > 0 && (
                <ul className="mt-2 space-y-1 pl-4">
                  {hijasDe(c.id).map((s) => (
                    <li key={s.id} className="flex items-center justify-between text-sm text-slate-600">
                      <span>↳ {s.nombre}</span>
                      <button onClick={() => eliminar(s.id)} className="text-red-600 hover:underline">Eliminar</button>
                    </li>
                  ))}
                </ul>
              )}
            </li>
          ))}
        </ul>
      </div>
    )
  }

  return (
    <div>
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold">Categorías y subcategorías</h2>
        <button onClick={() => setShow((s) => !s)} className="rounded-lg bg-indigo-600 px-3 py-2 text-sm font-medium text-white hover:bg-indigo-700">
          {show ? 'Cancelar' : 'Nueva categoría'}
        </button>
      </div>
      <p className="mt-1 text-sm text-slate-500">
        Elige una <strong>categoría padre</strong> para crearla como subcategoría. Los reportes y el
        dashboard agrupan por categoría y su subcategoría.
      </p>
      {error && <p className="mt-2 text-sm text-red-600">{error}</p>}

      {show && (
        <div className="mt-4 grid gap-3 rounded-xl border border-slate-200 bg-white p-4 sm:grid-cols-4">
          <input placeholder="Nombre" value={form.nombre} onChange={(e) => setForm((f) => ({ ...f, nombre: e.target.value }))} className="rounded-lg border border-slate-300 px-3 py-2 text-sm" />
          <select value={form.tipo} onChange={(e) => setForm((f) => ({ ...f, tipo: e.target.value, padre_id: '' }))} className="rounded-lg border border-slate-300 px-3 py-2 text-sm">
            <option value="gasto">Gasto</option>
            <option value="ingreso">Ingreso</option>
          </select>
          <select value={form.padre_id} onChange={(e) => setForm((f) => ({ ...f, padre_id: e.target.value }))} className="rounded-lg border border-slate-300 px-3 py-2 text-sm">
            <option value="">Es categoría principal</option>
            {padresGasto.map((c) => <option key={c.id} value={c.id}>Subcategoría de {c.nombre}</option>)}
          </select>
          <button onClick={crear} className="rounded-lg bg-indigo-600 px-3 py-2 text-sm text-white hover:bg-indigo-700">Guardar</button>
        </div>
      )}

      <div className="mt-4 grid gap-4 sm:grid-cols-2">
        {seccion('gasto')}
        {seccion('ingreso')}
      </div>
    </div>
  )
}
