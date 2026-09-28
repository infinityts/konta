import { useEffect, useState } from 'react'
import { api } from '../api'
import {
  fmtMoney,
  type Categoria,
  type Cuenta,
  type Etiqueta,
  type SaldoResumen,
  type Tarjeta,
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
  cuenta_destino_id: '',
  tarjeta_id: '',
  // '' = una sola vez (ocasional) · con valor = se repite con esa periodicidad
  repeticion: '',
}

export default function Transacciones() {
  const [items, setItems] = useState<Transaccion[]>([])
  const [categorias, setCategorias] = useState<Categoria[]>([])
  const [etiquetas, setEtiquetas] = useState<Etiqueta[]>([])
  const [cuentas, setCuentas] = useState<Cuenta[]>([])
  const [tarjetas, setTarjetas] = useState<Tarjeta[]>([])
  const [form, setForm] = useState(empty)
  const [editando, setEditando] = useState<string | null>(null)
  const [show, setShow] = useState(false)
  const [error, setError] = useState('')

  // crear etiqueta/subetiqueta sin salir del formulario
  const [nuevaEtq, setNuevaEtq] = useState(false)
  const [etqForm, setEtqForm] = useState({ nombre: '', padre_id: '' })

  // filtros del listado
  const [filtro, setFiltro] = useState<'todos' | 'gasto' | 'ingreso' | 'transferencia'>('todos')
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
    api<Tarjeta[]>('/tarjetas').then(setTarjetas)
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
      cuenta_destino_id: t.cuenta_destino_id ?? '',
      tarjeta_id: t.tarjeta_id ?? '',
      repeticion: '',
    })
    setShow(true)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  const esTransferencia = form.tipo === 'transferencia'

  async function guardar() {
    setError('')
    try {
      const cuerpo = {
        tipo: form.tipo,
        monto: form.monto,
        moneda: form.moneda,
        fecha: form.fecha,
        descripcion: form.descripcion || null,
        cuenta_id: form.cuenta_id || null,
        // Una transferencia mueve dinero entre dos cuentas propias: no es un gasto
        // que se clasifique, así que no lleva categoría, etiqueta ni tarjeta.
        cuenta_destino_id: esTransferencia ? form.cuenta_destino_id || null : null,
        categoria_id: esTransferencia ? null : form.categoria_id || null,
        etiqueta_id: esTransferencia ? null : form.etiqueta_id || null,
        tarjeta_id: esTransferencia ? null : form.tarjeta_id || null,
        // null = una sola vez; con periodicidad, la app crea el compromiso que se
        // repite solo y deja este movimiento como el pago de este periodo
        recurrencia: !esTransferencia && form.repeticion ? { periodicidad: form.repeticion } : null,
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
        body: JSON.stringify({
          nombre: etqForm.nombre,
          categoria_id: form.categoria_id,
          padre_id: etqForm.padre_id || null,
        }),
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

  /** Al cambiar de categoría se limpia la etiqueta: cada categoría tiene las suyas. */
  function setCategoria(id: string) {
    setForm((f) => ({ ...f, categoria_id: id, etiqueta_id: '' }))
  }

  /** Contabilidad: el débito descuenta de SU cuenta; el crédito no toca cuentas (es un pasivo). */
  function elegirTarjeta(id: string) {
    const t = tarjetas.find((x) => x.id === id)
    setForm((f) => {
      const nuevo = { ...f, tarjeta_id: id }
      if (t?.tipo === 'debito' && t.cuenta_id) nuevo.cuenta_id = t.cuenta_id
      if (t?.tipo === 'credito') nuevo.cuenta_id = ''
      return nuevo
    })
  }

  function setTipo(tipo: string) {
    setForm((f) => ({ ...f, tipo, categoria_id: '' }))
  }

  const nombreCat = (id: string | null) => categorias.find((x) => x.id === id)?.nombre ?? '—'
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
  const nombreTarjeta = (id: string | null) => tarjetas.find((t) => t.id === id)?.nombre ?? null

  const categoriasFiltradas = categorias.filter((c) => c.tipo === form.tipo)

  // Las etiquetas viven DENTRO de la categoría elegida
  const etqDeCategoria = etiquetas.filter((e) => e.categoria_id === form.categoria_id)
  const etqRaices = etqDeCategoria.filter((e) => !e.padre_id)
  const etqHijas = (id: string) => etqDeCategoria.filter((e) => e.padre_id === id)

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
            <option value="transferencia">Transferencia entre cuentas</option>
          </select>
          <input placeholder="Monto" value={form.monto} onChange={(e) => set('monto', e.target.value)} className="rounded-lg border border-slate-300 px-3 py-2 text-sm" />
          <input type="date" value={form.fecha} onChange={(e) => set('fecha', e.target.value)} className="rounded-lg border border-slate-300 px-3 py-2 text-sm" />
          <input placeholder="Descripción (ej. Internet Movistar)" value={form.descripcion} onChange={(e) => set('descripcion', e.target.value)} className="rounded-lg border border-slate-300 px-3 py-2 text-sm" />

          {!esTransferencia && (
            <div className="flex items-center gap-2 sm:col-span-2">
              <select
                value={form.repeticion}
                onChange={(e) => set('repeticion', e.target.value)}
                className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
                title="Un gasto ocasional se registra una vez; uno recurrente se genera solo cada periodo"
              >
                <option value="">Una sola vez (ocasional)</option>
                <optgroup label="Se repite…">
                  {(form.tipo === 'ingreso'
                    ? ['diario', 'semanal', 'mensual']
                    : ['semanal', 'mensual', 'trimestral', 'semestral', 'anual']
                  ).map((p) => (
                    <option key={p} value={p}>
                      {p === 'mensual' ? 'cada mes' : p === 'anual' ? 'cada año' : `cada ${p}`}
                    </option>
                  ))}
                </optgroup>
              </select>
              {form.repeticion ? (
                <span className="text-xs text-slate-500">
                  Se guarda este movimiento y además el compromiso que lo repetirá solo
                  {form.fecha ? ` a partir del ${form.fecha}` : ''} (el día sale de la fecha).
                </span>
              ) : (
                <span className="text-xs text-slate-400">
                  Un arriendo, un colegio o el streaming: elige «se repite» y no vuelves a
                  teclearlo cada mes.
                </span>
              )}
            </div>
          )}

          {esTransferencia ? (
            <>
              <select value={form.cuenta_id} onChange={(e) => set('cuenta_id', e.target.value)} className="rounded-lg border border-slate-300 px-3 py-2 text-sm">
                <option value="">Desde la cuenta…</option>
                {cuentas.map((c) => (
                  <option key={c.id} value={c.id}>{c.nombre} · {fmtMoney(c.saldo_actual)}</option>
                ))}
              </select>
              <select value={form.cuenta_destino_id} onChange={(e) => set('cuenta_destino_id', e.target.value)} className="rounded-lg border border-slate-300 px-3 py-2 text-sm">
                <option value="">Hacia la cuenta…</option>
                {cuentas.filter((c) => c.id !== form.cuenta_id).map((c) => (
                  <option key={c.id} value={c.id}>{c.nombre} · {fmtMoney(c.saldo_actual)}</option>
                ))}
              </select>
              <p className="text-xs text-slate-500 sm:col-span-2">
                Mover dinero entre tus cuentas <strong>no es un gasto ni un ingreso</strong>: no
                aparece en reportes, presupuestos ni flujo de caja. Las dos cuentas deben estar en
                la misma moneda (lo comprueba la app).
              </p>
            </>
          ) : (
            <>
          <select value={form.categoria_id} onChange={(e) => setCategoria(e.target.value)} className="rounded-lg border border-slate-300 px-3 py-2 text-sm">
            <option value="">Sin categoría</option>
            {categoriasFiltradas.map((c) => (
              <option key={c.id} value={c.id}>{c.nombre}</option>
            ))}
          </select>

          <select value={form.tarjeta_id} onChange={(e) => elegirTarjeta(e.target.value)} className="rounded-lg border border-slate-300 px-3 py-2 text-sm">
            <option value="">Sin tarjeta</option>
            {tarjetas.some((t) => t.tipo === 'debito') && (
              <optgroup label="Débito (descuenta de su cuenta)">
                {tarjetas.filter((t) => t.tipo === 'debito').map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.nombre}{t.cuenta_nombre ? ` → ${t.cuenta_nombre}` : ' (sin cuenta asociada)'}
                  </option>
                ))}
              </optgroup>
            )}
            {tarjetas.some((t) => t.tipo === 'credito') && (
              <optgroup label="Crédito (no toca tus cuentas)">
                {tarjetas.filter((t) => t.tipo === 'credito').map((t) => (
                  <option key={t.id} value={t.id}>{t.nombre}</option>
                ))}
              </optgroup>
            )}
          </select>

          <select value={form.cuenta_id} onChange={(e) => set('cuenta_id', e.target.value)} className="rounded-lg border border-slate-300 px-3 py-2 text-sm">
            <option value="">Sin cuenta (no afecta el saldo de una cuenta)</option>
            {cuentas.map((c) => (
              <option key={c.id} value={c.id}>{c.nombre} · {fmtMoney(c.saldo_actual)}</option>
            ))}
          </select>

          {form.tarjeta_id && tarjetas.find((t) => t.id === form.tarjeta_id)?.tipo === 'credito' && (
            <p className="text-xs text-slate-500 sm:col-span-2">
              💳 Tarjeta de crédito: es un <strong>pasivo</strong>, no descuenta de tus cuentas.
              Su deuda se registra en <strong>Tarjetas</strong>.
            </p>
          )}

          {/* Etiqueta / subetiqueta — solo las de la categoría elegida */}
          <select
            value={form.etiqueta_id}
            onChange={(e) => set('etiqueta_id', e.target.value)}
            disabled={!form.categoria_id}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm disabled:bg-slate-100 disabled:text-slate-400"
          >
            <option value="">{form.categoria_id ? 'Sin etiqueta' : 'Elige primero una categoría'}</option>
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
            <button
              onClick={() => setNuevaEtq((v) => !v)}
              disabled={!form.categoria_id}
              className="rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-700 hover:bg-slate-50 disabled:bg-slate-100 disabled:text-slate-400"
            >
              {nuevaEtq ? 'Cancelar etiqueta' : '＋ Nueva etiqueta / subetiqueta'}
            </button>
            {!form.categoria_id && (
              <span className="text-xs text-slate-500">Elige una categoría para ver o crear sus etiquetas</span>
            )}
          </div>
            </>
          )}

          {nuevaEtq && form.categoria_id && (
            <div className="flex flex-wrap items-center gap-2 rounded-lg bg-slate-50 p-3 sm:col-span-2">
              <span className="text-xs text-slate-500">
                Dentro de <strong>{nombreCat(form.categoria_id)}</strong>
              </span>
              <input placeholder="Nombre de la etiqueta" value={etqForm.nombre} onChange={(e) => setEtqForm((f) => ({ ...f, nombre: e.target.value }))} className="rounded-lg border border-slate-300 px-3 py-2 text-sm" />
              <select value={etqForm.padre_id} onChange={(e) => setEtqForm((f) => ({ ...f, padre_id: e.target.value }))} className="rounded-lg border border-slate-300 px-3 py-2 text-sm">
                <option value="">Es etiqueta</option>
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
        {(['todos', 'gasto', 'ingreso', 'transferencia'] as const).map((f) => (
          <button
            key={f}
            onClick={() => setFiltro(f)}
            className={`rounded-full px-3 py-1 text-sm ${filtro === f ? 'bg-indigo-600 text-white' : 'border border-slate-300 text-slate-600 hover:bg-slate-50'}`}
          >
            {f === 'todos' ? 'Todos' : f === 'gasto' ? 'Gastos' : f === 'ingreso' ? 'Ingresos' : 'Transferencias'}
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
                {(t.suscripcion_id || t.ingreso_recurrente_id) && (
                  <span
                    className="ml-2 rounded-full bg-sky-50 px-2 py-0.5 text-xs font-normal text-sky-700"
                    title="Viene de un compromiso recurrente"
                  >
                    🔁 recurrente
                  </span>
                )}
                {nombreEtiqueta(t.etiqueta_id) && (
                  <span className="ml-2 rounded-full bg-indigo-50 px-2 py-0.5 text-xs font-normal text-indigo-700">
                    #{nombreEtiqueta(t.etiqueta_id)}
                  </span>
                )}
              </p>
              <p className="text-sm text-slate-500">
                {t.fecha}
                {t.tipo === 'transferencia' ? (
                  <>
                    {' · '}🔄 {nombreCuenta(t.cuenta_id)}
                    {' → '}
                    {nombreCuenta(t.cuenta_destino_id ?? null)}
                  </>
                ) : (
                  <>
                    {' · '}{nombreCat(t.categoria_id)}
                    {nombreTarjeta(t.tarjeta_id) && <span className="ml-2 text-slate-400">· 💳 {nombreTarjeta(t.tarjeta_id)}</span>}
                    {nombreCuenta(t.cuenta_id) && <span className="ml-2 text-slate-400">· {nombreCuenta(t.cuenta_id)}</span>}
                  </>
                )}
              </p>
            </div>
            <div className="flex items-center gap-3">
              <span
                className={`text-sm font-medium ${
                  t.tipo === 'gasto'
                    ? 'text-red-600'
                    : t.tipo === 'ingreso'
                      ? 'text-emerald-600'
                      : 'text-slate-600'
                }`}
              >
                {t.tipo === 'gasto' ? '-' : t.tipo === 'ingreso' ? '+' : '🔄 '}
                {fmtMoney(t.monto)}
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
