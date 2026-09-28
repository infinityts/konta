import { useEffect, useState } from 'react'
import { api } from '../api'
import { fmtMoney, type Categoria, type IngresoRecurrente } from '../types'

const DIAS_SEMANA = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']

const empty = {
  nombre: '',
  monto: '',
  moneda: 'COP',
  periodicidad: 'mensual',
  dia: '',
  categoria_id: '',
}

function humanizar(p: IngresoRecurrente): string {
  if (p.periodicidad === 'diario') return 'Todos los días'
  if (p.periodicidad === 'semanal') return `Cada ${DIAS_SEMANA[p.dia ?? 0]}`
  return `Día ${p.dia} de cada mes`
}

export default function IngresosRecurrentes() {
  const [items, setItems] = useState<IngresoRecurrente[]>([])
  const [categorias, setCategorias] = useState<Categoria[]>([])
  const [form, setForm] = useState(empty)
  const [show, setShow] = useState(false)
  const [error, setError] = useState('')

  async function cargar() {
    try {
      setItems(await api<IngresoRecurrente[]>('/ingresos-recurrentes'))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Error')
    }
  }

  useEffect(() => {
    cargar()
    api<Categoria[]>('/categorias').then((cs) => setCategorias(cs.filter((c) => c.tipo === 'ingreso')))
  }, [])

  async function crear() {
    setError('')
    try {
      await api('/ingresos-recurrentes', {
        method: 'POST',
        body: JSON.stringify({
          nombre: form.nombre,
          monto: form.monto,
          moneda: form.moneda,
          periodicidad: form.periodicidad,
          dia: form.periodicidad === 'diario' ? null : Number(form.dia),
          categoria_id: form.categoria_id || null,
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
    await api(`/ingresos-recurrentes/${id}`, { method: 'DELETE' })
    cargar()
  }

  async function toggleActiva(item: IngresoRecurrente) {
    await api(`/ingresos-recurrentes/${item.id}`, {
      method: 'PATCH',
      body: JSON.stringify({ activa: !item.activa }),
    })
    cargar()
  }

  const set = (k: keyof typeof empty, v: string) => setForm((f) => ({ ...f, [k]: v }))
  function setPeriodicidad(p: string) {
    setForm((f) => ({ ...f, periodicidad: p, dia: '' }))
  }
  const nombreCat = (id: string | null) => categorias.find((c) => c.id === id)?.nombre ?? '—'

  return (
    <div>
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold">Ingresos recurrentes</h2>
        <button onClick={() => setShow((s) => !s)} className="rounded-lg bg-indigo-600 px-3 py-2 text-sm font-medium text-white hover:bg-indigo-700">
          {show ? 'Cancelar' : 'Nuevo ingreso'}
        </button>
      </div>

      {show && (
        <div className="mt-4 grid gap-3 rounded-xl border border-slate-200 bg-white p-4 sm:grid-cols-2">
          <input placeholder="Nombre (ej. Salario, Diario de taxi)" value={form.nombre} onChange={(e) => set('nombre', e.target.value)} className="rounded-lg border border-slate-300 px-3 py-2 text-sm" />
          <input placeholder="Monto" value={form.monto} onChange={(e) => set('monto', e.target.value)} className="rounded-lg border border-slate-300 px-3 py-2 text-sm" />

          <select value={form.periodicidad} onChange={(e) => setPeriodicidad(e.target.value)} className="rounded-lg border border-slate-300 px-3 py-2 text-sm">
            <option value="diario">Diario</option>
            <option value="semanal">Semanal</option>
            <option value="mensual">Mensual</option>
          </select>

          {form.periodicidad === 'semanal' && (
            <select value={form.dia} onChange={(e) => set('dia', e.target.value)} className="rounded-lg border border-slate-300 px-3 py-2 text-sm">
              <option value="">Día de la semana…</option>
              {DIAS_SEMANA.map((d, i) => (
                <option key={d} value={i}>{d}</option>
              ))}
            </select>
          )}
          {form.periodicidad === 'mensual' && (
            <input type="number" min={1} max={31} placeholder="Día del mes (1-31)" value={form.dia} onChange={(e) => set('dia', e.target.value)} className="rounded-lg border border-slate-300 px-3 py-2 text-sm" />
          )}

          <select value={form.moneda} onChange={(e) => set('moneda', e.target.value)} className="rounded-lg border border-slate-300 px-3 py-2 text-sm">
            <option value="COP">COP</option>
            <option value="USD">USD</option>
            <option value="EUR">EUR</option>
          </select>
          <select value={form.categoria_id} onChange={(e) => set('categoria_id', e.target.value)} className="rounded-lg border border-slate-300 px-3 py-2 text-sm">
            <option value="">Sin categoría</option>
            {categorias.map((c) => (
              <option key={c.id} value={c.id}>{c.nombre}</option>
            ))}
          </select>
          <button onClick={crear} className="rounded-lg bg-indigo-600 px-3 py-2 text-sm text-white hover:bg-indigo-700 sm:col-span-2">Guardar</button>
        </div>
      )}

      {error && <p className="mt-3 text-sm text-red-600">{error}</p>}

      <ul className="mt-4 space-y-2">
        {items.map((i) => (
          <li key={i.id} className="flex items-center justify-between rounded-xl border border-slate-200 bg-white p-4">
            <div>
              <p className={`font-medium ${i.activa ? '' : 'text-slate-400 line-through'}`}>{i.nombre}</p>
              <p className="text-sm text-slate-500">
                {humanizar(i)} · {nombreCat(i.categoria_id)} · próximo {i.proxima_ejecucion}
              </p>
            </div>
            <div className="flex items-center gap-3">
              <span className="text-sm font-medium">{fmtMoney(i.monto)}</span>
              <button onClick={() => toggleActiva(i)} className="text-sm text-slate-500 hover:underline">
                {i.activa ? 'Pausar' : 'Activar'}
              </button>
              <button onClick={() => eliminar(i.id)} className="text-sm text-red-600 hover:underline">Eliminar</button>
            </div>
          </li>
        ))}
      </ul>
    </div>
  )
}
