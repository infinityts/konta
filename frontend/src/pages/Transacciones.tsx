import { useEffect, useState } from 'react'
import { api } from '../api'
import { fmtMoney, type Categoria, type Cuenta, type Etiqueta, type SaldoResumen, type Transaccion } from '../types'

const empty = {
  tipo: 'gasto',
  monto: '',
  moneda: 'COP',
  fecha: new Date().toISOString().slice(0, 10),
  descripcion: '',
  categoria_id: '',
  etiqueta_id: '',
  cuenta_id: '',
}

export default function Transacciones() {
  const [items, setItems] = useState<Transaccion[]>([])
  const [categorias, setCategorias] = useState<Categoria[]>([])
  const [etiquetas, setEtiquetas] = useState<Etiqueta[]>([])
  const [cuentas, setCuentas] = useState<Cuenta[]>([])
  const [form, setForm] = useState(empty)
  const [show, setShow] = useState(false)
  const [error, setError] = useState('')

  async function cargar() {
    try {
      setItems(await api<Transaccion[]>('/transacciones'))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Error')
    }
  }

  useEffect(() => {
    cargar()
    api<Categoria[]>('/categorias').then(setCategorias)
    api<Etiqueta[]>('/etiquetas').then(setEtiquetas)
    api<SaldoResumen>('/cuentas').then((r) => setCuentas(r.cuentas))
  }, [])

  async function crear() {
    setError('')
    try {
      await api('/transacciones', {
        method: 'POST',
        body: JSON.stringify({
          tipo: form.tipo,
          monto: form.monto,
          moneda: form.moneda,
          fecha: form.fecha,
          descripcion: form.descripcion || null,
          categoria_id: form.categoria_id || null,
          etiqueta_id: form.etiqueta_id || null,
          cuenta_id: form.cuenta_id || null,
        }),
      })
      setForm({ ...empty, tipo: form.tipo, fecha: form.fecha })
      setShow(false)
      cargar()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Error al guardar')
    }
  }

  async function eliminar(id: string) {
    await api(`/transacciones/${id}`, { method: 'DELETE' })
    cargar()
  }

  const set = (k: keyof typeof empty, v: string) => setForm((f) => ({ ...f, [k]: v }))
  function setTipo(tipo: string) {
    setForm((f) => ({ ...f, tipo, categoria_id: '' }))
  }

  const nombreCat = (id: string | null) => {
    if (!id) return '—'
    const c = categorias.find((x) => x.id === id)
    if (!c) return '—'
    if (c.padre_id) {
      const padre = categorias.find((x) => x.id === c.padre_id)
      if (padre) return `${padre.nombre} › ${c.nombre}`
    }
    return c.nombre
  }
  const nombreEtiqueta = (id: string | null) => etiquetas.find((e) => e.id === id)?.nombre ?? null
  const nombreCuenta = (id: string | null) => cuentas.find((c) => c.id === id)?.nombre ?? null
  const categoriasFiltradas = categorias.filter((c) => c.tipo === form.tipo)
  const catRaices = categoriasFiltradas.filter((c) => !c.padre_id)
  const subcatsDe = (id: string) => categoriasFiltradas.filter((c) => c.padre_id === id)
  const raices = etiquetas.filter((e) => !e.padre_id)
  const hijasDe = (id: string) => etiquetas.filter((e) => e.padre_id === id)

  return (
    <div>
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold">Transacciones</h2>
        <button onClick={() => setShow((s) => !s)} className="rounded-lg bg-indigo-600 px-3 py-2 text-sm font-medium text-white hover:bg-indigo-700">
          {show ? 'Cancelar' : 'Nueva transacción'}
        </button>
      </div>

      {show && (
        <div className="mt-4 grid gap-3 rounded-xl border border-slate-200 bg-white p-4 sm:grid-cols-2">
          <select value={form.tipo} onChange={(e) => setTipo(e.target.value)} className="rounded-lg border border-slate-300 px-3 py-2 text-sm">
            <option value="gasto">Gasto</option>
            <option value="ingreso">Ingreso</option>
          </select>
          <input placeholder="Monto" value={form.monto} onChange={(e) => set('monto', e.target.value)} className="rounded-lg border border-slate-300 px-3 py-2 text-sm" />
          <input type="date" value={form.fecha} onChange={(e) => set('fecha', e.target.value)} className="rounded-lg border border-slate-300 px-3 py-2 text-sm" />
          <input placeholder="Descripción (ej. Salario, Mercado...)" value={form.descripcion} onChange={(e) => set('descripcion', e.target.value)} className="rounded-lg border border-slate-300 px-3 py-2 text-sm" />
          <select value={form.categoria_id} onChange={(e) => set('categoria_id', e.target.value)} className="rounded-lg border border-slate-300 px-3 py-2 text-sm">
            <option value="">Sin categoría</option>
            {catRaices.map((r) => (
              <optgroup key={r.id} label={r.nombre}>
                <option value={r.id}>{r.nombre}</option>
                {subcatsDe(r.id).map((h) => (
                  <option key={h.id} value={h.id}>— {h.nombre}</option>
                ))}
              </optgroup>
            ))}
          </select>
          <select value={form.cuenta_id} onChange={(e) => set('cuenta_id', e.target.value)} className="rounded-lg border border-slate-300 px-3 py-2 text-sm">
            <option value="">Sin cuenta (no afecta el saldo de una cuenta)</option>
            {cuentas.map((c) => (
              <option key={c.id} value={c.id}>{c.nombre} · {fmtMoney(c.saldo_actual)}</option>
            ))}
          </select>
          <select value={form.etiqueta_id} onChange={(e) => set('etiqueta_id', e.target.value)} className="rounded-lg border border-slate-300 px-3 py-2 text-sm">
            <option value="">Sin etiqueta</option>
            {raices.map((r) => (
              <optgroup key={r.id} label={r.nombre}>
                <option value={r.id}>{r.nombre}</option>
                {hijasDe(r.id).map((h) => (
                  <option key={h.id} value={h.id}>— {h.nombre}</option>
                ))}
              </optgroup>
            ))}
          </select>
          <button onClick={crear} className="rounded-lg bg-indigo-600 px-3 py-2 text-sm text-white hover:bg-indigo-700 sm:col-span-2">Guardar</button>
        </div>
      )}

      {error && <p className="mt-3 text-sm text-red-600">{error}</p>}

      <ul className="mt-4 space-y-2">
        {items.map((t) => (
          <li key={t.id} className="flex items-center justify-between rounded-xl border border-slate-200 bg-white p-4">
            <div>
              <p className="font-medium">
                {t.descripcion ?? nombreCat(t.categoria_id)}
                {nombreEtiqueta(t.etiqueta_id) && (
                  <span className="ml-2 rounded-full bg-indigo-50 px-2 py-0.5 text-xs font-normal text-indigo-700">
                    #{nombreEtiqueta(t.etiqueta_id)}
                  </span>
                )}
              </p>
              <p className="text-sm text-slate-500">
                {t.fecha} · {nombreCat(t.categoria_id)}
                {nombreCuenta(t.cuenta_id) && <span className="ml-2 text-slate-400">· {nombreCuenta(t.cuenta_id)}</span>}
              </p>
            </div>
            <div className="flex items-center gap-3">
              <span className={`text-sm font-medium ${t.tipo === 'gasto' ? 'text-red-600' : 'text-emerald-600'}`}>
                {t.tipo === 'gasto' ? '-' : '+'}{fmtMoney(t.monto)}
              </span>
              <button onClick={() => eliminar(t.id)} className="text-sm text-red-600 hover:underline">Eliminar</button>
            </div>
          </li>
        ))}
      </ul>
    </div>
  )
}
