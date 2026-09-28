import { useEffect, useState } from 'react'
import { api } from '../api'
import { fmtMoney, type Categoria, type Suscripcion, type Tarjeta } from '../types'

const empty = {
  nombre: '',
  monto: '',
  moneda: 'COP',
  periodicidad: 'mensual',
  proximo_pago: '',
  categoria_id: '',
  tarjeta_id: '',
}

export default function Suscripciones() {
  const [items, setItems] = useState<Suscripcion[]>([])
  const [categorias, setCategorias] = useState<Categoria[]>([])
  const [tarjetas, setTarjetas] = useState<Tarjeta[]>([])
  const [form, setForm] = useState(empty)
  const [show, setShow] = useState(false)
  const [error, setError] = useState('')

  async function cargar() {
    try {
      setItems(await api<Suscripcion[]>('/suscripciones'))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Error')
    }
  }

  useEffect(() => {
    cargar()
    api<Categoria[]>('/categorias').then(setCategorias)
    api<Tarjeta[]>('/tarjetas').then(setTarjetas)
  }, [])

  async function crear() {
    setError('')
    try {
      await api('/suscripciones', {
        method: 'POST',
        body: JSON.stringify({
          nombre: form.nombre,
          monto: form.monto,
          moneda: form.moneda,
          periodicidad: form.periodicidad,
          proximo_pago: form.proximo_pago || null,
          categoria_id: form.categoria_id || null,
          tarjeta_id: form.tarjeta_id || null,
        }),
      })
      setForm(empty)
      setShow(false)
      cargar()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Error al guardar')
    }
  }

  async function eliminar(id: string) {
    await api(`/suscripciones/${id}`, { method: 'DELETE' })
    cargar()
  }

  const set = (k: keyof typeof empty, v: string) => setForm((f) => ({ ...f, [k]: v }))
  const nombreTarjeta = (id: string | null) => tarjetas.find((t) => t.id === id)?.nombre ?? '—'

  return (
    <div>
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold">Suscripciones</h2>
        <button onClick={() => setShow((s) => !s)} className="rounded-lg bg-indigo-600 px-3 py-2 text-sm font-medium text-white hover:bg-indigo-700">
          {show ? 'Cancelar' : 'Nueva suscripción'}
        </button>
      </div>

      {show && (
        <div className="mt-4 grid gap-3 rounded-xl border border-slate-200 bg-white p-4 sm:grid-cols-2">
          <input placeholder="Nombre (ej. Netflix)" value={form.nombre} onChange={(e) => set('nombre', e.target.value)} className="rounded-lg border border-slate-300 px-3 py-2 text-sm" />
          <input placeholder="Monto" value={form.monto} onChange={(e) => set('monto', e.target.value)} className="rounded-lg border border-slate-300 px-3 py-2 text-sm" />
          <select value={form.periodicidad} onChange={(e) => set('periodicidad', e.target.value)} className="rounded-lg border border-slate-300 px-3 py-2 text-sm">
            <option value="mensual">Mensual</option>
            <option value="anual">Anual</option>
            <option value="trimestral">Trimestral</option>
            <option value="semanal">Semanal</option>
          </select>
          <select value={form.moneda} onChange={(e) => set('moneda', e.target.value)} className="rounded-lg border border-slate-300 px-3 py-2 text-sm">
            <option value="COP">COP</option>
            <option value="USD">USD</option>
            <option value="EUR">EUR</option>
          </select>
          <input type="date" value={form.proximo_pago} onChange={(e) => set('proximo_pago', e.target.value)} className="rounded-lg border border-slate-300 px-3 py-2 text-sm" />
          <select value={form.categoria_id} onChange={(e) => set('categoria_id', e.target.value)} className="rounded-lg border border-slate-300 px-3 py-2 text-sm">
            <option value="">Sin categoría</option>
            {categorias.map((c) => (
              <option key={c.id} value={c.id}>{c.nombre}</option>
            ))}
          </select>
          <select value={form.tarjeta_id} onChange={(e) => set('tarjeta_id', e.target.value)} className="rounded-lg border border-slate-300 px-3 py-2 text-sm">
            <option value="">Sin tarjeta</option>
            {tarjetas.map((t) => (
              <option key={t.id} value={t.id}>{t.nombre}</option>
            ))}
          </select>
          <button onClick={crear} className="rounded-lg bg-indigo-600 px-3 py-2 text-sm text-white hover:bg-indigo-700 sm:col-span-2">Guardar</button>
        </div>
      )}

      {error && <p className="mt-3 text-sm text-red-600">{error}</p>}

      <ul className="mt-4 space-y-2">
        {items.map((s) => (
          <li key={s.id} className="flex items-center justify-between rounded-xl border border-slate-200 bg-white p-4">
            <div>
              <p className="font-medium">{s.nombre}</p>
              <p className="text-sm text-slate-500">
                {s.periodicidad} · {nombreTarjeta(s.tarjeta_id)}
                {s.proximo_pago ? ` · próximo ${s.proximo_pago}` : ''}
              </p>
            </div>
            <div className="flex items-center gap-3">
              <span className="text-sm font-medium">{fmtMoney(s.monto)}</span>
              <button onClick={() => eliminar(s.id)} className="text-sm text-red-600 hover:underline">Eliminar</button>
            </div>
          </li>
        ))}
      </ul>
    </div>
  )
}
