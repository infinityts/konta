import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import type { Categoria, CopiarEtiquetas } from '../types'

export default function Categorias() {
  const [items, setItems] = useState<Categoria[]>([])
  const [form, setForm] = useState({ nombre: '', tipo: 'gasto' })
  const [editando, setEditando] = useState<string | null>(null)
  const [show, setShow] = useState(false)
  const [error, setError] = useState('')
  const [aviso, setAviso] = useState('')
  // Copiar las etiquetas de otra categoría (Casa 2 con lo de Casa 1)
  const [copiar, setCopiar] = useState<{ destino: string; origen: string; plan: CopiarEtiquetas | null } | null>(null)

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

  function nueva() {
    setEditando(null)
    setForm({ nombre: '', tipo: 'gasto' })
    setError('')
    setShow(true)
  }

  function abrirEditar(c: Categoria) {
    setEditando(c.id)
    setForm({ nombre: c.nombre, tipo: c.tipo })
    setError('')
    setShow(true)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  async function guardar() {
    setError('')
    try {
      if (editando) {
        await api(`/categorias/${editando}`, { method: 'PATCH', body: JSON.stringify(form) })
      } else {
        await api('/categorias', { method: 'POST', body: JSON.stringify(form) })
      }
      setShow(false)
      setEditando(null)
      setForm({ nombre: '', tipo: 'gasto' })
      cargar()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Error al guardar')
    }
  }

  async function eliminar(id: string) {
    if (!confirm('¿Eliminar esta categoría? Sus etiquetas también se borran.')) return
    try {
      await api(`/categorias/${id}`, { method: 'DELETE' })
      cargar()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Error al eliminar')
    }
  }

  /** Enseña qué se crearía, sin tocar nada (la previsualización no guarda). */
  async function previsualizar(destino: string, origen: string) {
    setError('')
    setAviso('')
    if (!origen) {
      setCopiar({ destino, origen: '', plan: null })
      return
    }
    try {
      const plan = await api<CopiarEtiquetas>(`/categorias/${destino}/copiar-etiquetas`, {
        method: 'POST',
        body: JSON.stringify({ origen_id: origen, previsualizar: true }),
      })
      setCopiar({ destino, origen, plan })
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Error al previsualizar')
    }
  }

  async function copiarEtiquetas() {
    if (!copiar?.origen) return
    setError('')
    try {
      const r = await api<CopiarEtiquetas>(`/categorias/${copiar.destino}/copiar-etiquetas`, {
        method: 'POST',
        body: JSON.stringify({ origen_id: copiar.origen }),
      })
      setAviso(
        r.total_creadas > 0
          ? `✅ ${r.total_creadas} etiqueta(s) copiadas. Ve a Etiquetas para verlas.`
          : 'No había nada que copiar: ya estaban todas.',
      )
      setCopiar(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Error al copiar')
    }
  }

  const seccion = (tipo: 'gasto' | 'ingreso') => (
    <div>
      <h3 className={`font-medium ${tipo === 'gasto' ? 'text-red-600' : 'text-emerald-600'}`}>
        {tipo === 'gasto' ? 'Gastos' : 'Ingresos'}
      </h3>
      <ul className="mt-2 space-y-1">
        {items.filter((c) => c.tipo === tipo).map((c) => (
          <li key={c.id} className="rounded-lg border border-slate-200 bg-white px-3 py-2">
            <div className="flex items-center justify-between">
              <span className="text-sm text-slate-800">{c.nombre}</span>
              <div className="flex items-center gap-3">
                <button
                  onClick={() =>
                    copiar?.destino === c.id
                      ? setCopiar(null)
                      : setCopiar({ destino: c.id, origen: '', plan: null })
                  }
                  className="text-xs text-slate-600 hover:underline"
                  title="Traer aquí las etiquetas de otra categoría, sin volver a crearlas"
                >
                  {copiar?.destino === c.id ? 'Cancelar' : 'Copiar etiquetas de…'}
                </button>
                <button onClick={() => abrirEditar(c)} className="text-xs text-indigo-600 hover:underline">Editar</button>
                <button onClick={() => eliminar(c.id)} className="text-xs text-red-600 hover:underline">Eliminar</button>
              </div>
            </div>

            {copiar?.destino === c.id && (
              <div className="mt-2 border-t border-slate-100 pt-2">
                <select
                  value={copiar.origen}
                  onChange={(e) => previsualizar(c.id, e.target.value)}
                  className="w-full rounded-lg border border-slate-300 px-2 py-1.5 text-sm"
                >
                  <option value="">Traer las etiquetas de…</option>
                  {items
                    .filter((o) => o.id !== c.id && o.tipo === c.tipo)
                    .map((o) => (
                      <option key={o.id} value={o.id}>{o.nombre}</option>
                    ))}
                </select>

                {copiar.plan && (
                  <div className="mt-2 text-xs">
                    {copiar.plan.total_creadas === 0 ? (
                      <p className="text-slate-500">
                        No hay nada que copiar: esta categoría ya tiene todo lo de la otra.
                      </p>
                    ) : (
                      <>
                        <p className="text-slate-600">
                          Se crearán <strong>{copiar.plan.total_creadas}</strong> etiqueta(s):
                        </p>
                        <ul className="mt-1 space-y-0.5 text-slate-500">
                          {copiar.plan.plan.map((ruta) => (
                            <li key={ruta}>＋ {ruta}</li>
                          ))}
                        </ul>
                        {copiar.plan.omitidas.length > 0 && (
                          <p className="mt-1 text-slate-400">
                            Ya existen (no se duplican): {copiar.plan.omitidas.join(', ')}
                          </p>
                        )}
                        <button
                          onClick={copiarEtiquetas}
                          className="mt-2 rounded-lg bg-indigo-600 px-3 py-1.5 text-sm text-white hover:bg-indigo-700"
                        >
                          Copiar {copiar.plan.total_creadas} etiqueta(s)
                        </button>
                      </>
                    )}
                  </div>
                )}
              </div>
            )}
          </li>
        ))}
        {items.filter((c) => c.tipo === tipo).length === 0 && (
          <li className="text-sm text-slate-400">Sin categorías</li>
        )}
      </ul>
    </div>
  )

  return (
    <div>
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold">Categorías</h2>
        <button
          onClick={() => (show ? (setShow(false), setEditando(null)) : nueva())}
          className="rounded-lg bg-indigo-600 px-3 py-2 text-sm font-medium text-white hover:bg-indigo-700"
        >
          {show ? 'Cancelar' : 'Nueva categoría'}
        </button>
      </div>

      <p className="mt-1 text-sm text-slate-500">
        Las <strong>categorías</strong> son el nivel superior (Vivienda, Transporte, Casa 1…).
        El anidamiento vive en las etiquetas:
        <code className="mx-1 rounded bg-slate-100 px-1">Categoría › Etiqueta › Subetiqueta</code>
        — se manejan en <Link to="/etiquetas" className="text-indigo-600 underline">Etiquetas</Link>.
      </p>
      {error && <p className="mt-2 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
      {aviso && <p className="mt-2 rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-700">{aviso}</p>}

      {show && (
        <div className="mt-4 grid gap-3 rounded-xl border border-slate-200 bg-white p-4 sm:grid-cols-3">
          {editando && <p className="text-sm font-medium text-indigo-700 sm:col-span-3">Editando categoría</p>}
          <input
            placeholder="Nombre (ej. Vivienda, Casa 1…)"
            value={form.nombre}
            onChange={(e) => setForm((f) => ({ ...f, nombre: e.target.value }))}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
          />
          <select
            value={form.tipo}
            onChange={(e) => setForm((f) => ({ ...f, tipo: e.target.value }))}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
          >
            <option value="gasto">Gasto</option>
            <option value="ingreso">Ingreso</option>
          </select>
          <button
            onClick={guardar}
            disabled={!form.nombre}
            className="rounded-lg bg-indigo-600 px-3 py-2 text-sm text-white hover:bg-indigo-700 disabled:bg-slate-300"
          >
            {editando ? 'Guardar cambios' : 'Crear'}
          </button>
        </div>
      )}

      <div className="mt-4 grid gap-4 sm:grid-cols-2">
        {seccion('gasto')}
        {seccion('ingreso')}
      </div>
    </div>
  )
}
