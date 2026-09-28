import { useEffect, useState } from 'react'
import { api } from '../api'
import {
  fmtMoney,
  type Categoria,
  type Cuenta,
  type Etiqueta,
  type SaldoResumen,
  type Transaccion,
} from '../types'

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
  const [editando, setEditando] = useState<string | null>(null)
  const [show, setShow] = useState(false)
  const [error, setError] = useState('')

  // crear etiqueta/subetiqueta sin salir del formulario
  const [nuevaEtq, setNuevaEtq] = useState(false)
  const [etqForm, setEtqForm] = useState({ nombre: '', padre_id: '' })

  // filtros del listado
  const [filtro, setFiltro] = useState<'todos' | 'gasto' | 'ingreso'>('todos')
  const [busqueda, setBusqueda] = useState('')

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
    api<SaldoResumen>('/cuentas').then((r) => {
      setCuentas(r.cuentas)
      // Con una sola cuenta se preselecciona, para que el movimiento afecte el saldo real
      if (r.cuentas.length === 1) setForm((f) => ({ ...f, cuenta_id: r.cuentas[0].id }))
    })
  }, [])

  function nueva() {
    setEditando(null)
    setForm({ ...empty, cuenta_id: cuentas.length === 1 ? cuentas[0].id : '' })
    setError('')
    setNuevaEtq(false)
    setShow(true)
  }

  function abrirEditar(t: Transaccion) {
    setError('')
    setEditando(t.id)
    setNuevaEtq(false)
    setForm({
      tipo: t.tipo,
      monto: String(t.monto),
      moneda: t.moneda,
      fecha: t.fecha,
      descripcion: t.descripcion ?? '',
      categoria_id: t.categoria_id ?? '',
      etiqueta_id: t.etiqueta_id ?? '',
      cuenta_id: t.cuenta_id ?? '',
    })
    setShow(true)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  async function guardar() {
    setError('')
    try {
      const cuerpo = {
        tipo: form.tipo,
        monto: form.monto,
        moneda: form.moneda,
        fecha: form.fecha,
        descripcion: form.descripcion || null,
        categoria_id: form.categoria_id || null,
        etiqueta_id: form.etiqueta_id || null,
        cuenta_id: form.cuenta_id || null,
      }
      if (editando) {
        await api(`/transacciones/${editando}`, { method: 'PATCH', body: JSON.stringify(cuerpo) })
      } else {
        await api('/transacciones', { method: 'POST', body: JSON.stringify(cuerpo) })
      }
      setForm({ ...empty, tipo: form.tipo, fecha: form.fecha, cuenta_id: form.cuenta_id })
      setEditando(null)
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

  async function crearEtiqueta() {
    if (!etqForm.nombre) return
    setError('')
    try {
      const creada = await api<Etiqueta>('/etiquetas', {
        method: 'POST',
        body: JSON.stringify({ nombre: etqForm.nombre, padre_id: etqForm.padre_id || null }),
      })
      setEtiquetas(await api<Etiqueta[]>('/etiquetas'))
      setForm((f) => ({ ...f, etiqueta_id: creada.id }))
      setEtqForm({ nombre: '', padre_id: '' })
      setNuevaEtq(false)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Error al crear la etiqueta')
    }
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
  const nombreEtiqueta = (id: string | null) => {
    const e = etiquetas.find((x) => x.id === id)
    if (!e) return null
    if (e.padre_id) {
      const p = etiquetas.find((x) => x.id === e.padre_id)
      if (p) return `${p.nombre} › ${e.nombre}`
    }
    return e.nombre
  }
  const nombreCuenta = (id: string | null) => cuentas.find((c) => c.id === id)?.nombre ?? null

  const categoriasFiltradas = categorias.filter((c) => c.tipo === form.tipo)
  const catRaices = categoriasFiltradas.filter((c) => !c.padre_id)
  const subcatsDe = (id: string) => categoriasFiltradas.filter((c) => c.padre_id === id)
  const etqRaices = etiquetas.filter((e) => !e.padre_id)
  const etqHijas = (id: string) => etiquetas.filter((e) => e.padre_id === id)

  const visibles = items.filter((t) => {
    if (filtro !== 'todos' && t.tipo !== filtro) return false
    const q = busqueda.trim().toLowerCase()
    if (!q) return true
    return (
      (t.descripcion ?? '').toLowerCase().includes(q) ||
      nombreCat(t.categoria_id).toLowerCase().includes(q)
    )
  })

  return (
    <div>
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold">Transacciones</h2>
        <button
          onClick={() => (show ? (setShow(false), setEditando(null)) : nueva())}
          className="rounded-lg bg-indigo-600 px-3 py-2 text-sm font-medium text-white hover:bg-indigo-700"
        >
          {show ? 'Cancelar' : 'Nueva transacción'}
        </button>
      </div>

      {show && (
        <div className="mt-4 grid gap-3 rounded-xl border border-slate-200 bg-white p-4 sm:grid-cols-2">
          {editando && (
            <p className="text-sm font-medium text-indigo-700 sm:col-span-2">
              Editando movimiento — cambia lo que necesites y guarda
            </p>
          )}
          <select value={form.tipo} onChange={(e) => setTipo(e.target.value)} className="rounded-lg border border-slate-300 px-3 py-2 text-sm">
            <option value="gasto">Gasto</option>
            <option value="ingreso">Ingreso</option>
          </select>
          <input placeholder="Monto" value={form.monto} onChange={(e) => set('monto', e.target.value)} className="rounded-lg border border-slate-300 px-3 py-2 text-sm" />
          <input type="date" value={form.fecha} onChange={(e) => set('fecha', e.target.value)} className="rounded-lg border border-slate-300 px-3 py-2 text-sm" />
          <input placeholder="Descripción (ej. Internet Movistar)" value={form.descripcion} onChange={(e) => set('descripcion', e.target.value)} className="rounded-lg border border-slate-300 px-3 py-2 text-sm" />

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

          {/* Etiqueta / subetiqueta */}
          <select value={form.etiqueta_id} onChange={(e) => set('etiqueta_id', e.target.value)} className="rounded-lg border border-slate-300 px-3 py-2 text-sm">
            <option value="">Sin etiqueta</option>
            {etqRaices.map((r) => (
              <optgroup key={r.id} label={r.nombre}>
                <option value={r.id}>{r.nombre}</option>
                {etqHijas(r.id).map((h) => (
                  <option key={h.id} value={h.id}>— {h.nombre}</option>
                ))}
              </optgroup>
            ))}
          </select>

          <div className="flex items-center gap-2 sm:col-span-2">
            <button onClick={() => setNuevaEtq((v) => !v)} className="rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-700 hover:bg-slate-50">
              {nuevaEtq ? 'Cancelar etiqueta' : '＋ Nueva etiqueta / subetiqueta'}
            </button>
          </div>

          {nuevaEtq && (
            <div className="flex flex-wrap items-center gap-2 rounded-lg bg-slate-50 p-3 sm:col-span-2">
              <input placeholder="Nombre de la etiqueta" value={etqForm.nombre} onChange={(e) => setEtqForm((f) => ({ ...f, nombre: e.target.value }))} className="rounded-lg border border-slate-300 px-3 py-2 text-sm" />
              <select value={etqForm.padre_id} onChange={(e) => setEtqForm((f) => ({ ...f, padre_id: e.target.value }))} className="rounded-lg border border-slate-300 px-3 py-2 text-sm">
                <option value="">Es etiqueta principal</option>
                {etqRaices.map((e) => <option key={e.id} value={e.id}>Subetiqueta de {e.nombre}</option>)}
              </select>
              <button onClick={crearEtiqueta} className="rounded-lg bg-slate-800 px-3 py-2 text-sm text-white hover:bg-slate-900">Crear y asignar</button>
            </div>
          )}

          {form.cuenta_id === '' && cuentas.length > 0 && (
            <p className="text-xs text-amber-600 sm:col-span-2">
              ⚠️ Sin cuenta seleccionada: este movimiento no moverá el saldo de ninguna cuenta.
            </p>
          )}
          <button onClick={guardar} className="rounded-lg bg-indigo-600 px-3 py-2 text-sm text-white hover:bg-indigo-700 sm:col-span-2">
            {editando ? 'Guardar cambios' : 'Guardar'}
          </button>
        </div>
      )}

      {error && <p className="mt-3 text-sm text-red-600">{error}</p>}

      {/* Filtros */}
      <div className="mt-4 flex flex-wrap items-center gap-2">
        {(['todos', 'gasto', 'ingreso'] as const).map((f) => (
          <button
            key={f}
            onClick={() => setFiltro(f)}
            className={`rounded-full px-3 py-1 text-sm ${filtro === f ? 'bg-indigo-600 text-white' : 'border border-slate-300 text-slate-600 hover:bg-slate-50'}`}
          >
            {f === 'todos' ? 'Todos' : f === 'gasto' ? 'Gastos' : 'Ingresos'}
          </button>
        ))}
        <input
          placeholder="Buscar…"
          value={busqueda}
          onChange={(e) => setBusqueda(e.target.value)}
          className="ml-auto w-48 rounded-lg border border-slate-300 px-3 py-1.5 text-sm"
        />
      </div>

      <ul className="mt-3 space-y-2">
        {visibles.map((t) => (
          <li key={t.id} className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-slate-200 bg-white p-4">
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
              <button onClick={() => abrirEditar(t)} className="text-sm text-indigo-600 hover:underline">Editar</button>
              <button onClick={() => eliminar(t.id)} className="text-sm text-red-600 hover:underline">Eliminar</button>
            </div>
          </li>
        ))}
        {visibles.length === 0 && <p className="text-sm text-slate-500">No hay movimientos que coincidan.</p>}
      </ul>
    </div>
  )
}
