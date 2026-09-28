import { useEffect, useState } from 'react'
import { api } from '../api'
import { fmtMoney, type Categoria, type Presupuesto } from '../types'

const empty = { categoria_id: '', monto_limite: '' }

function colorBarra(p: number): string {
  if (p >= 100) return 'bg-red-500'
  if (p >= 70) return 'bg-amber-500'
  return 'bg-emerald-500'
}

export default function Presupuestos() {
  const [items, setItems] = useState<Presupuesto[]>([])
  const [categorias, setCategorias] = useState<Categoria[]>([])
  const [form, setForm] = useState(empty)
  const [show, setShow] = useState(false)
  const [error, setError] = useState('')

  async function cargar() {
    try {
      setItems(await api<Presupuesto[]>('/presupuestos'))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Error')
    }
  }

  useEffect(() => {
    cargar()
    api<Categoria[]>('/categorias').then((cs) => setCategorias(cs.filter((c) => c.tipo === 'gasto')))
  }, [])

  async function crear() {
    setError('')
    try {
      await api('/presupuestos', {
        method: 'POST',
        body: JSON.stringify({ categoria_id: form.categoria_id, monto_limite: form.monto_limite }),
      })
      setForm(empty)
      setShow(false)
      cargar()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Error al guardar')
    }
  }

  async function eliminar(id: string) {
    await api(`/presupuestos/${id}`, { method: 'DELETE' })
    cargar()
  }

  const set = (k: keyof typeof empty, v: string) => setForm((f) => ({ ...f, [k]: v }))
  const excedidos = items.filter((i) => i.porcentaje >= 100).length

  return (
    <div>
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold">Presupuestos</h2>
        <button onClick={() => setShow((s) => !s)} className="rounded-lg bg-indigo-600 px-3 py-2 text-sm font-medium text-white hover:bg-indigo-700">
          {show ? 'Cancelar' : 'Nuevo presupuesto'}
        </button>
      </div>

      {excedidos > 0 && (
        <p className="mt-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          ⚠️ {excedidos} presupuesto(s) excedido(s) este mes.
        </p>
      )}

      {show && (
        <div className="mt-4 grid gap-3 rounded-xl border border-slate-200 bg-white p-4 sm:grid-cols-3">
          <select value={form.categoria_id} onChange={(e) => set('categoria_id', e.target.value)} className="rounded-lg border border-slate-300 px-3 py-2 text-sm">
            <option value="">Categoría…</option>
            {categorias.map((c) => (
              <option key={c.id} value={c.id}>{c.nombre}</option>
            ))}
          </select>
          <input placeholder="Límite mensual" value={form.monto_limite} onChange={(e) => set('monto_limite', e.target.value)} className="rounded-lg border border-slate-300 px-3 py-2 text-sm" />
          <button onClick={crear} className="rounded-lg bg-indigo-600 px-3 py-2 text-sm text-white hover:bg-indigo-700">Guardar</button>
        </div>
      )}

      {error && <p className="mt-3 text-sm text-red-600">{error}</p>}

      <ul className="mt-4 space-y-3">
        {items.map((p) => (
          <li key={p.id} className="rounded-xl border border-slate-200 bg-white p-4">
            <div className="flex items-center justify-between">
              <span className="font-medium">{p.categoria_nombre}</span>
              <div className="flex items-center gap-3">
                <span className="text-sm text-slate-600">
                  {fmtMoney(p.gastado)} / {fmtMoney(p.monto_limite)}
                  <span className={`ml-2 font-medium ${p.porcentaje >= 100 ? 'text-red-600' : p.porcentaje >= 70 ? 'text-amber-600' : 'text-emerald-600'}`}>
                    {p.porcentaje}%
                  </span>
                </span>
                <button onClick={() => eliminar(p.id)} className="text-sm text-red-600 hover:underline">Eliminar</button>
              </div>
            </div>
            <div className="mt-2 h-2 w-full rounded-full bg-slate-100">
              <div className={`h-2 rounded-full ${colorBarra(p.porcentaje)}`} style={{ width: `${Math.min(p.porcentaje, 100)}%` }} />
            </div>
            <p className="mt-1 text-xs text-slate-500">
              {p.restante >= 0 ? `Te quedan ${fmtMoney(p.restante)}` : `Excedido en ${fmtMoney(Math.abs(p.restante))}`}
            </p>
          </li>
        ))}
        {items.length === 0 && <p className="text-sm text-slate-500">Aún no tienes presupuestos.</p>}
      </ul>
    </div>
  )
}
