import { useEffect, useState } from 'react'
import { api } from '../api'
import {
  fmtMoney,
  type Asegurado,
  type Beneficiario,
  type Categoria,
  type Cuenta,
  type Etiqueta,
  type Poliza,
  type PolizaResumen,
  type SaldoResumen,
  type Tarjeta,
  type TipoPoliza,
} from '../types'

const TIPOS: { valor: TipoPoliza; label: string }[] = [
  { valor: 'vida', label: 'Vida' },
  { valor: 'salud', label: 'Salud' },
  { valor: 'vehiculo', label: 'Vehículo' },
  { valor: 'hogar', label: 'Hogar' },
  { valor: 'otro', label: 'Otro' },
]

const empty = {
  tipo: 'vida' as TipoPoliza,
  aseguradora: '',
  numero_poliza: '',
  asegurado_nombre: '',
  placa: '',
  marca: '',
  modelo: '',
  anio: '',
  valor_asegurado: '',
  prima: '',
  moneda: 'COP',
  periodicidad: 'mensual',
  fecha_inicio: '',
  fecha_fin: '',
  proximo_pago: '',
  renovacion_automatica: false,
  categoria_id: '',
  etiqueta_id: '',
  tarjeta_id: '',
  cuenta_id: '',
  estado: 'activa',
  notas: '',
}

export default function Polizas() {
  const [items, setItems] = useState<Poliza[]>([])
  const [resumen, setResumen] = useState<PolizaResumen | null>(null)
  const [categorias, setCategorias] = useState<Categoria[]>([])
  const [etiquetas, setEtiquetas] = useState<Etiqueta[]>([])
  const [tarjetas, setTarjetas] = useState<Tarjeta[]>([])
  const [cuentas, setCuentas] = useState<Cuenta[]>([])
  const [form, setForm] = useState(empty)
  const [editando, setEditando] = useState<string | null>(null)
  const [show, setShow] = useState(false)
  const [abierta, setAbierta] = useState<string | null>(null)
  const [error, setError] = useState('')

  async function cargar() {
    try {
      setItems(await api<Poliza[]>('/polizas'))
      setResumen(await api<PolizaResumen>('/polizas/resumen'))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Error')
    }
  }

  useEffect(() => {
    cargar()
    api<Categoria[]>('/categorias').then(setCategorias)
    api<Etiqueta[]>('/etiquetas').then(setEtiquetas)
    api<Tarjeta[]>('/tarjetas').then(setTarjetas)
    api<SaldoResumen>('/cuentas').then((r) => setCuentas(r.cuentas))
  }, [])

  const set = <K extends keyof typeof form>(campo: K, valor: (typeof form)[K]) =>
    setForm((f) => ({ ...f, [campo]: valor }))

  const esVehiculo = form.tipo === 'vehiculo'

  async function guardar() {
    setError('')
    const cuerpo = {
      tipo: form.tipo,
      aseguradora: form.aseguradora,
      numero_poliza: form.numero_poliza || null,
      asegurado_nombre: form.asegurado_nombre || null,
      placa: esVehiculo ? form.placa || null : null,
      marca: esVehiculo ? form.marca || null : null,
      modelo: esVehiculo ? form.modelo || null : null,
      anio: esVehiculo && form.anio ? Number(form.anio) : null,
      valor_asegurado: esVehiculo && form.valor_asegurado ? form.valor_asegurado : null,
      prima: form.prima,
      moneda: form.moneda,
      periodicidad: form.periodicidad,
      fecha_inicio: form.fecha_inicio || null,
      fecha_fin: form.fecha_fin || null,
      proximo_pago: form.proximo_pago || null,
      renovacion_automatica: form.renovacion_automatica,
      categoria_id: form.categoria_id || null,
      etiqueta_id: form.etiqueta_id || null,
      tarjeta_id: form.tarjeta_id || null,
      cuenta_id: form.cuenta_id || null,
      estado: form.estado,
      notas: form.notas || null,
    }
    try {
      if (editando) {
        await api(`/polizas/${editando}`, { method: 'PATCH', body: JSON.stringify(cuerpo) })
      } else {
        await api('/polizas', { method: 'POST', body: JSON.stringify(cuerpo) })
      }
      cerrarForm()
      cargar()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Error al guardar')
    }
  }

  function cerrarForm() {
    setShow(false)
    setEditando(null)
    setForm(empty)
  }

  function editar(p: Poliza) {
    setEditando(p.id)
    setShow(true)
    setForm({
      tipo: p.tipo,
      aseguradora: p.aseguradora,
      numero_poliza: p.numero_poliza ?? '',
      asegurado_nombre: p.asegurado_nombre ?? '',
      placa: p.placa ?? '',
      marca: p.marca ?? '',
      modelo: p.modelo ?? '',
      anio: p.anio != null ? String(p.anio) : '',
      valor_asegurado: p.valor_asegurado != null ? String(p.valor_asegurado) : '',
      prima: String(p.prima),
      moneda: p.moneda,
      periodicidad: p.periodicidad,
      fecha_inicio: p.fecha_inicio ?? '',
      fecha_fin: p.fecha_fin ?? '',
      proximo_pago: p.proximo_pago ?? '',
      renovacion_automatica: p.renovacion_automatica,
      categoria_id: p.categoria_id ?? '',
      etiqueta_id: p.etiqueta_id ?? '',
      tarjeta_id: p.tarjeta_id ?? '',
      cuenta_id: p.cuenta_id ?? '',
      estado: p.estado,
      notas: p.notas ?? '',
    })
  }

  const alternarEstado = (p: Poliza) =>
    api(`/polizas/${p.id}`, {
      method: 'PATCH',
      body: JSON.stringify({ estado: p.estado === 'activa' ? 'pausada' : 'activa' }),
    }).then(cargar)

  const eliminar = (id: string) =>
    api(`/polizas/${id}`, { method: 'DELETE' }).then(() => {
      if (abierta === id) setAbierta(null)
      cargar()
    })

  // Las etiquetas viven dentro de la categoría elegida
  const etqDeCategoria = etiquetas.filter((e) => e.categoria_id === form.categoria_id)

  const input = 'mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm'

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-xl font-semibold">Seguros y pólizas</h2>
        <button
          onClick={() => (show ? cerrarForm() : setShow(true))}
          className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700"
        >
          {show ? 'Cancelar' : '＋ Nueva póliza'}
        </button>
      </div>
      <p className="mt-1 text-sm text-slate-500">
        Seguros de vida, salud, vehículo u hogar. La prima genera su gasto al vencer, como una
        suscripción, y avisa del vencimiento de la vigencia.
      </p>

      {resumen && (
        <div className="mt-4 grid gap-3 sm:grid-cols-3">
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <p className="text-xs uppercase tracking-wide text-slate-500">Pólizas activas</p>
            <p className="mt-1 text-2xl font-semibold text-slate-800">{resumen.polizas_activas}</p>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <p className="text-xs uppercase tracking-wide text-slate-500">Primas al mes</p>
            <p className="mt-1 text-2xl font-semibold text-slate-800">
              {fmtMoney(resumen.prima_mensual_cop)}
            </p>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <p className="text-xs uppercase tracking-wide text-slate-500">Al año</p>
            <p className="mt-1 text-2xl font-semibold text-slate-800">
              {fmtMoney(resumen.prima_anual_cop)}
            </p>
          </div>
        </div>
      )}
      {resumen && resumen.sin_tasa.length > 0 && (
        <p className="mt-2 rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-700">
          Sin tasa de cambio registrada para {resumen.sin_tasa.join(', ')}: esas primas no se
          incluyen en el total. Regístrala en <strong>Monedas</strong>.
        </p>
      )}

      {error && <p className="mt-3 text-sm text-red-600">{error}</p>}

      {show && (
        <div className="mt-4 rounded-xl border border-slate-200 bg-white p-5">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <div>
              <label className="text-sm text-slate-600">Tipo</label>
              <select
                value={form.tipo}
                onChange={(e) => set('tipo', e.target.value as TipoPoliza)}
                className={input}
              >
                {TIPOS.map((t) => (
                  <option key={t.valor} value={t.valor}>
                    {t.label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-sm text-slate-600">Aseguradora</label>
              <input
                value={form.aseguradora}
                onChange={(e) => set('aseguradora', e.target.value)}
                placeholder="Sura, Bolívar, Colsanitas…"
                className={input}
              />
            </div>
            <div>
              <label className="text-sm text-slate-600">Número de póliza</label>
              <input
                value={form.numero_poliza}
                onChange={(e) => set('numero_poliza', e.target.value)}
                className={input}
              />
            </div>

            <div>
              <label className="text-sm text-slate-600">
                {esVehiculo ? 'Tomador / propietario' : 'Persona asegurada'}
              </label>
              <input
                value={form.asegurado_nombre}
                onChange={(e) => set('asegurado_nombre', e.target.value)}
                className={input}
              />
            </div>

            {esVehiculo && (
              <>
                <div>
                  <label className="text-sm text-slate-600">Placa</label>
                  <input
                    value={form.placa}
                    onChange={(e) => set('placa', e.target.value.toUpperCase())}
                    placeholder="ABC123"
                    className={input}
                  />
                </div>
                <div>
                  <label className="text-sm text-slate-600">Marca</label>
                  <input value={form.marca} onChange={(e) => set('marca', e.target.value)} className={input} />
                </div>
                <div>
                  <label className="text-sm text-slate-600">Modelo / línea</label>
                  <input value={form.modelo} onChange={(e) => set('modelo', e.target.value)} className={input} />
                </div>
                <div>
                  <label className="text-sm text-slate-600">Año</label>
                  <input
                    type="number"
                    value={form.anio}
                    onChange={(e) => set('anio', e.target.value)}
                    className={input}
                  />
                </div>
                <div>
                  <label className="text-sm text-slate-600">Valor asegurado</label>
                  <input
                    value={form.valor_asegurado}
                    onChange={(e) => set('valor_asegurado', e.target.value)}
                    placeholder="45000000"
                    className={input}
                  />
                </div>
              </>
            )}

            <div>
              <label className="text-sm text-slate-600">Prima</label>
              <input
                value={form.prima}
                onChange={(e) => set('prima', e.target.value)}
                placeholder="1200000"
                className={input}
              />
            </div>
            <div>
              <label className="text-sm text-slate-600">Moneda</label>
              <input value={form.moneda} onChange={(e) => set('moneda', e.target.value.toUpperCase())} className={input} />
            </div>
            <div>
              <label className="text-sm text-slate-600">Periodicidad</label>
              <select
                value={form.periodicidad}
                onChange={(e) => set('periodicidad', e.target.value)}
                className={input}
              >
                <option value="mensual">Mensual</option>
                <option value="trimestral">Trimestral</option>
                <option value="semestral">Semestral</option>
                <option value="anual">Anual</option>
              </select>
            </div>

            <div>
              <label className="text-sm text-slate-600">Inicio de vigencia</label>
              <input
                type="date"
                value={form.fecha_inicio}
                onChange={(e) => set('fecha_inicio', e.target.value)}
                className={input}
              />
            </div>
            <div>
              <label className="text-sm text-slate-600">Fin de vigencia</label>
              <input
                type="date"
                value={form.fecha_fin}
                onChange={(e) => set('fecha_fin', e.target.value)}
                className={input}
              />
            </div>
            <div>
              <label className="text-sm text-slate-600">Próximo pago de prima</label>
              <input
                type="date"
                value={form.proximo_pago}
                onChange={(e) => set('proximo_pago', e.target.value)}
                className={input}
              />
            </div>

            <div>
              <label className="text-sm text-slate-600">Categoría</label>
              <select
                value={form.categoria_id}
                onChange={(e) => setForm((f) => ({ ...f, categoria_id: e.target.value, etiqueta_id: '' }))}
                className={input}
              >
                <option value="">Sin categoría</option>
                {categorias
                  .filter((c) => c.tipo === 'gasto')
                  .map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.nombre}
                    </option>
                  ))}
              </select>
            </div>
            <div>
              <label className="text-sm text-slate-600">Etiqueta</label>
              <select
                value={form.etiqueta_id}
                onChange={(e) => set('etiqueta_id', e.target.value)}
                className={input}
              >
                <option value="">{form.categoria_id ? 'Sin etiqueta' : 'Elige una categoría'}</option>
                {etqDeCategoria.map((e) => (
                  <option key={e.id} value={e.id}>
                    {e.padre_id
                      ? `${etiquetas.find((x) => x.id === e.padre_id)?.nombre ?? ''} › ${e.nombre}`
                      : e.nombre}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-sm text-slate-600">Tarjeta (opcional)</label>
              <select
                value={form.tarjeta_id}
                onChange={(e) => set('tarjeta_id', e.target.value)}
                className={input}
              >
                <option value="">Sin tarjeta</option>
                {tarjetas.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.nombre}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-sm text-slate-600">Cuenta (de dónde sale el pago)</label>
              <select
                value={form.cuenta_id}
                onChange={(e) => set('cuenta_id', e.target.value)}
                className={input}
              >
                <option value="">Sin cuenta</option>
                {cuentas.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.nombre}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-sm text-slate-600">Estado</label>
              <select value={form.estado} onChange={(e) => set('estado', e.target.value)} className={input}>
                <option value="activa">Activa</option>
                <option value="pausada">Pausada</option>
                <option value="cancelada">Cancelada</option>
              </select>
            </div>

            <div className="flex items-end">
              <label className="flex items-center gap-2 text-sm text-slate-600">
                <input
                  type="checkbox"
                  checked={form.renovacion_automatica}
                  onChange={(e) => set('renovacion_automatica', e.target.checked)}
                />
                Renovación automática
              </label>
            </div>
            <div className="sm:col-span-2">
              <label className="text-sm text-slate-600">Notas</label>
              <input value={form.notas} onChange={(e) => set('notas', e.target.value)} className={input} />
            </div>
          </div>

          <div className="mt-4 flex gap-2">
            <button
              onClick={guardar}
              className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700"
            >
              {editando ? 'Guardar cambios' : 'Crear póliza'}
            </button>
            <button
              onClick={cerrarForm}
              className="rounded-lg border border-slate-300 px-4 py-2 text-sm text-slate-700 hover:bg-slate-50"
            >
              Cancelar
            </button>
          </div>
        </div>
      )}

      <ul className="mt-4 space-y-3">
        {items.map((p) => (
          <li key={p.id} className="rounded-xl border border-slate-200 bg-white p-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="font-medium">
                  {p.titulo}
                  <span className="ml-2 rounded bg-slate-100 px-2 py-0.5 text-xs uppercase tracking-wide text-slate-600">
                    {TIPOS.find((t) => t.valor === p.tipo)?.label ?? p.tipo}
                  </span>
                  {p.estado !== 'activa' && (
                    <span className="ml-2 rounded bg-amber-100 px-2 py-0.5 text-xs text-amber-700">
                      {p.estado}
                    </span>
                  )}
                </p>
                <p className="text-sm text-slate-500">
                  {fmtMoney(p.prima)} {p.moneda} · {p.periodicidad}
                  {p.prima_mensual_cop != null && p.moneda !== 'COP' && (
                    <> · {fmtMoney(p.prima_mensual_cop)}/mes en COP</>
                  )}
                  {p.numero_poliza ? ` · Póliza ${p.numero_poliza}` : ''}
                </p>
                <p className="text-sm text-slate-500">
                  {p.proximo_pago ? `Próxima prima: ${p.proximo_pago}` : 'Sin próximo pago'}
                  {p.fecha_inicio || p.fecha_fin
                    ? ` · Vigencia: ${p.fecha_inicio ?? '—'} → ${p.fecha_fin ?? '—'}`
                    : ''}
                  {p.renovacion_automatica ? ' · renovación automática' : ''}
                </p>
                {p.tipo === 'vehiculo' && (p.placa || p.marca) && (
                  <p className="text-sm text-slate-500">
                    {[p.placa, p.marca, p.modelo, p.anio].filter(Boolean).join(' · ')}
                    {p.valor_asegurado != null ? ` · asegurado por ${fmtMoney(p.valor_asegurado)}` : ''}
                  </p>
                )}
              </div>
              <div className="flex shrink-0 gap-3">
                <button onClick={() => editar(p)} className="text-sm text-indigo-600 hover:underline">
                  Editar
                </button>
                <button onClick={() => alternarEstado(p)} className="text-sm text-slate-600 hover:underline">
                  {p.estado === 'activa' ? 'Pausar' : 'Activar'}
                </button>
                <button onClick={() => setAbierta(abierta === p.id ? null : p.id)} className="text-sm text-slate-600 hover:underline">
                  {abierta === p.id ? 'Ocultar' : 'Personas cubiertas'}
                </button>
                <button onClick={() => eliminar(p.id)} className="text-sm text-red-600 hover:underline">
                  Eliminar
                </button>
              </div>
            </div>

            {abierta === p.id && (
              <>
                <Asegurados poliza={p} onCambio={cargar} />
                <Beneficiarios poliza={p} onCambio={cargar} />
              </>
            )}
          </li>
        ))}
        {items.length === 0 && (
          <p className="text-sm text-slate-500">Aún no has registrado pólizas.</p>
        )}
      </ul>
    </div>
  )
}

/** Personas cubiertas por la póliza (una póliza familiar cubre a varias). */
function Asegurados({ poliza, onCambio }: { poliza: Poliza; onCambio: () => void }) {
  const [nombre, setNombre] = useState('')
  const [parentesco, setParentesco] = useState('')
  const [nacimiento, setNacimiento] = useState('')
  const [titular, setTitular] = useState(false)
  const [error, setError] = useState('')

  async function agregar() {
    setError('')
    try {
      await api(`/polizas/${poliza.id}/asegurados`, {
        method: 'POST',
        body: JSON.stringify({
          nombre,
          parentesco: parentesco || null,
          fecha_nacimiento: nacimiento || null,
          es_titular: titular,
        }),
      })
      setNombre('')
      setParentesco('')
      setNacimiento('')
      setTitular(false)
      onCambio()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Error')
    }
  }

  async function marcarTitular(a: Asegurado) {
    setError('')
    try {
      await api(`/polizas/asegurados/${a.id}`, {
        method: 'PATCH',
        body: JSON.stringify({
          nombre: a.nombre,
          parentesco: a.parentesco,
          fecha_nacimiento: a.fecha_nacimiento,
          es_titular: true,
        }),
      })
      onCambio()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Error')
    }
  }

  const borrar = (a: Asegurado) =>
    api(`/polizas/asegurados/${a.id}`, { method: 'DELETE' }).then(onCambio)

  return (
    <div className="mt-3 rounded-lg border border-slate-200 bg-slate-50 p-3">
      <p className="text-sm text-slate-600">
        Personas aseguradas · <strong>{poliza.asegurados.length}</strong>
      </p>
      {poliza.asegurados.length > 0 && (
        <ul className="mt-2 space-y-1">
          {poliza.asegurados.map((a) => (
            <li key={a.id} className="flex items-center justify-between text-sm">
              <span className="text-slate-700">
                {a.nombre}
                {a.parentesco ? ` · ${a.parentesco}` : ''}
                {a.fecha_nacimiento ? ` · ${a.fecha_nacimiento}` : ''}
                {a.es_titular && (
                  <span className="ml-2 rounded bg-indigo-100 px-2 py-0.5 text-xs text-indigo-700">
                    titular
                  </span>
                )}
              </span>
              <span className="flex gap-3">
                {!a.es_titular && (
                  <button onClick={() => marcarTitular(a)} className="text-xs text-indigo-600 hover:underline">
                    Hacer titular
                  </button>
                )}
                <button onClick={() => borrar(a)} className="text-xs text-red-600 hover:underline">
                  Quitar
                </button>
              </span>
            </li>
          ))}
        </ul>
      )}
      <div className="mt-2 flex flex-wrap items-end gap-2">
        <input
          value={nombre}
          onChange={(e) => setNombre(e.target.value)}
          placeholder="Nombre"
          className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
        />
        <input
          value={parentesco}
          onChange={(e) => setParentesco(e.target.value)}
          placeholder="Parentesco"
          className="w-32 rounded-lg border border-slate-300 px-3 py-2 text-sm"
        />
        <input
          type="date"
          value={nacimiento}
          onChange={(e) => setNacimiento(e.target.value)}
          className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
        />
        <label className="flex items-center gap-1 text-sm text-slate-600">
          <input type="checkbox" checked={titular} onChange={(e) => setTitular(e.target.checked)} />
          titular
        </label>
        <button
          onClick={agregar}
          disabled={!nombre}
          className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700 hover:bg-slate-50 disabled:opacity-50"
        >
          Añadir
        </button>
      </div>
      {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
    </div>
  )
}

/** Beneficiarios de una póliza (típicamente de vida), con su porcentaje. */
function Beneficiarios({ poliza, onCambio }: { poliza: Poliza; onCambio: () => void }) {
  const [nombre, setNombre] = useState('')
  const [parentesco, setParentesco] = useState('')
  const [porcentaje, setPorcentaje] = useState('')
  const [error, setError] = useState('')

  const suma = poliza.beneficiarios.reduce((a, b) => a + Number(b.porcentaje ?? 0), 0)

  async function agregar() {
    setError('')
    try {
      await api(`/polizas/${poliza.id}/beneficiarios`, {
        method: 'POST',
        body: JSON.stringify({
          nombre,
          parentesco: parentesco || null,
          porcentaje: porcentaje || null,
        }),
      })
      setNombre('')
      setParentesco('')
      setPorcentaje('')
      onCambio()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Error')
    }
  }

  const borrar = (b: Beneficiario) =>
    api(`/polizas/beneficiarios/${b.id}`, { method: 'DELETE' }).then(onCambio)

  return (
    <div className="mt-3 rounded-lg border border-slate-200 bg-slate-50 p-3">
      <p className="text-sm text-slate-600">
        Beneficiarios · repartido <strong>{suma}%</strong>
        {suma < 100 && ' (queda ' + (100 - suma) + '% por asignar)'}
      </p>
      {poliza.beneficiarios.length > 0 && (
        <ul className="mt-2 space-y-1">
          {poliza.beneficiarios.map((b) => (
            <li key={b.id} className="flex items-center justify-between text-sm">
              <span className="text-slate-700">
                {b.nombre}
                {b.parentesco ? ` · ${b.parentesco}` : ''}
                {b.porcentaje != null ? ` · ${Number(b.porcentaje)}%` : ''}
              </span>
              <button onClick={() => borrar(b)} className="text-xs text-red-600 hover:underline">
                Quitar
              </button>
            </li>
          ))}
        </ul>
      )}
      <div className="mt-2 flex flex-wrap items-end gap-2">
        <input
          value={nombre}
          onChange={(e) => setNombre(e.target.value)}
          placeholder="Nombre"
          className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
        />
        <input
          value={parentesco}
          onChange={(e) => setParentesco(e.target.value)}
          placeholder="Parentesco"
          className="w-32 rounded-lg border border-slate-300 px-3 py-2 text-sm"
        />
        <input
          value={porcentaje}
          onChange={(e) => setPorcentaje(e.target.value)}
          placeholder="%"
          className="w-20 rounded-lg border border-slate-300 px-3 py-2 text-sm"
        />
        <button
          onClick={agregar}
          disabled={!nombre}
          className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700 hover:bg-slate-50 disabled:opacity-50"
        >
          Añadir
        </button>
      </div>
      {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
    </div>
  )
}
