import { useEffect, useState, type ChangeEvent } from 'react'
import { api, apiUpload } from '../api'
import { useAuth } from '../auth'
import {
  fmtMoney,
  type AnalisisExtracto,
  type ControlConciliacion,
  type Cuenta,
  type Extracto,
  type ExtractoDetalle,
  type CandidatoRecurrente,
  type CrearRecurrentesResultado,
  type ImportarPreview,
  type ImportarResultado,
  type Tarjeta,
} from '../types'
import { Cargando } from '../components/loading-ui/cargando'

/** Color del badge según el tipo de movimiento. */
const TIPOS: Record<string, { label: string; clase: string }> = {
  compra: { label: 'compra', clase: 'bg-slate-100 text-slate-700' },
  pago: { label: 'pago', clase: 'bg-emerald-100 text-emerald-700' },
  interes: { label: 'interés', clase: 'bg-rose-100 text-rose-700' },
  comision: { label: 'comisión', clase: 'bg-amber-100 text-amber-700' },
  impuesto: { label: 'impuesto', clase: 'bg-amber-100 text-amber-700' },
  ajuste: { label: 'ajuste', clase: 'bg-violet-100 text-violet-700' },
  nomina: { label: 'nómina', clase: 'bg-sky-100 text-sky-700' },
  transferencia: { label: 'transferencia', clase: 'bg-sky-100 text-sky-700' },
  retiro: { label: 'retiro', clase: 'bg-slate-100 text-slate-700' },
  otro: { label: 'otro', clase: 'bg-slate-100 text-slate-500' },
}

const pct = (parte: number | string | null, total: number | string | null) => {
  const p = Number(parte)
  const t = Number(total)
  if (!Number.isFinite(p) || !Number.isFinite(t) || t === 0) return null
  return Math.round((p / t) * 100)
}

function Tarjeta({
  titulo,
  valor,
  detalle,
  tono = 'normal',
}: {
  titulo: string
  valor: string
  detalle?: string
  tono?: 'normal' | 'alerta' | 'bueno'
}) {
  const color =
    tono === 'alerta' ? 'text-rose-600' : tono === 'bueno' ? 'text-emerald-600' : 'text-slate-800'
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <p className="text-xs uppercase tracking-wide text-slate-500">{titulo}</p>
      <p className={`mt-1 text-xl font-semibold ${color}`}>{valor}</p>
      {detalle && <p className="mt-1 text-xs text-slate-500">{detalle}</p>}
    </div>
  )
}

function Control({ c }: { c: ControlConciliacion }) {
  const icono = c.ok === true ? '✅' : c.ok === false ? '❌' : '➖'
  const color =
    c.ok === true ? 'text-emerald-700' : c.ok === false ? 'text-rose-700' : 'text-slate-500'
  return (
    <li className={`flex flex-wrap items-baseline gap-x-2 text-sm ${color}`}>
      <span>{icono}</span>
      <span className="font-medium">{c.nombre}</span>
      <span className="text-slate-500">
        calculado {fmtMoney(c.calculado)}
        {c.declarado != null && <> · el extracto dice {fmtMoney(c.declarado)}</>}
        {c.diferencia && Number(c.diferencia) !== 0 && (
          <span className="text-rose-600"> · diferencia {fmtMoney(c.diferencia)}</span>
        )}
      </span>
      {c.ok === null && <span className="text-xs text-slate-400">(sin datos en el archivo)</span>}
    </li>
  )
}

export default function Extractos() {
  const { user } = useAuth()
  const [items, setItems] = useState<Extracto[]>([])
  const [cuentas, setCuentas] = useState<Cuenta[]>([])
  const [tarjetas, setTarjetas] = useState<Tarjeta[]>([])
  const [detalle, setDetalle] = useState<ExtractoDetalle | null>(null)
  const [analisis, setAnalisis] = useState<AnalisisExtracto | null>(null)
  const moneda = user?.moneda_principal ?? 'COP' 
  const [verInformativos, setVerInformativos] = useState(false)
  const [archivo, setArchivo] = useState<File | null>(null)
  const [contrasena, setContrasena] = useState('')
  const [cuentaId, setCuentaId] = useState('')
  const [tarjetaId, setTarjetaId] = useState('')
  const [tipo, setTipo] = useState('tarjeta')
  const [subiendo, setSubiendo] = useState(false)
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState('')
  // Fase 2: qué se importaría, a dónde y el resultado
  const [previa, setPrevia] = useState<ImportarPreview | null>(null)
  const [resultado, setResultado] = useState<ImportarResultado | null>(null)
  const [destinoCuenta, setDestinoCuenta] = useState('')
  const [destinoTarjeta, setDestinoTarjeta] = useState('')
  const [importando, setImportando] = useState(false)
  // Las cuotas de compras de meses anteriores se pagan este mes (es lo que hace que
  // cuadre con el pago mínimo), así que por defecto entran
  const [incluirAnteriores, setIncluirAnteriores] = useState(true)
  // Fase 3: recurrentes detectados
  const [recurrentes, setRecurrentes] = useState<CandidatoRecurrente[]>([])
  const [elegidos, setElegidos] = useState<Record<string, boolean>>({})
  const [creando, setCreando] = useState(false)
  const [avisoRecurrentes, setAvisoRecurrentes] = useState('')

  async function cargar() {
    setItems(await api<Extracto[]>('/extractos'))
  }

  useEffect(() => {
    Promise.all([
      cargar(),
      api<Cuenta[]>('/cuentas').then(setCuentas),
      api<Tarjeta[]>('/tarjetas').then(setTarjetas),
    ]).finally(() => setCargando(false))
  }, [])

  async function abrir(id: string) {
    setError('')
    setDetalle(null)
    setAnalisis(null)
    setPrevia(null)
    setResultado(null)
    setRecurrentes([])
    try {
      const [d, a, p, rec] = await Promise.all([
        api<ExtractoDetalle>(`/extractos/${id}`),
        api<AnalisisExtracto>(`/extractos/${id}/analisis?moneda=${moneda}`),
        api<ImportarPreview>(`/extractos/${id}/importar?incluir_cuotas_anteriores=${incluirAnteriores}`),
        api<CandidatoRecurrente[]>(`/extractos/${id}/recurrentes`),
      ])
      setDetalle(d)
      setAnalisis(a)
      setPrevia(p)
      setRecurrentes(rec)
      // Se preseleccionan los de confianza alta y media que no estén ya creados
      setElegidos(
        Object.fromEntries(
          rec.filter((c) => c.confianza !== 'baja' && !c.ya_es_suscripcion).map((c) => [c.clave, true])
        )
      )
      setAvisoRecurrentes('')
      if (d.tarjeta_id) setDestinoTarjeta(d.tarjeta_id)
      if (d.cuenta_id) setDestinoCuenta(d.cuenta_id)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo abrir el extracto')
    }
  }

  async function subir(e: React.FormEvent) {
    e.preventDefault()
    if (!archivo) {
      setError('Elige el archivo del extracto (PDF o Excel)')
      return
    }
    setSubiendo(true)
    setError('')
    try {
      const datos = new FormData()
      datos.append('archivo', archivo)
      if (contrasena) datos.append('contrasena', contrasena)
      if (cuentaId) datos.append('cuenta_id', cuentaId)
      if (tarjetaId) datos.append('tarjeta_id', tarjetaId)
      datos.append('tipo', tipo)
      const creado = await apiUpload<ExtractoDetalle>('/extractos', datos)
      setArchivo(null)
      setContrasena('')
      await cargar()
      await abrir(creado.id)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo leer el extracto')
    } finally {
      setSubiendo(false)
    }
  }

  async function crearRecurrentes() {
    if (!detalle) return
    const claves = Object.entries(elegidos)
      .filter(([, v]) => v)
      .map(([k]) => k)
    if (claves.length === 0) return
    setCreando(true)
    setError('')
    try {
      const r = await api<CrearRecurrentesResultado>(
        `/extractos/${detalle.id}/recurrentes`,
        { method: 'POST', body: JSON.stringify({ claves }) }
      )
      setAvisoRecurrentes(
        r.creadas.length > 0
          ? `Se crearon ${r.creadas.length}: ${r.creadas.map((s) => s.nombre).join(', ')}${
              r.omitidas.length > 0 ? ` · ${r.omitidas.join(' · ')}` : ''
            }`
          : r.omitidas.join(' · ')
      )
      setRecurrentes(await api<CandidatoRecurrente[]>(`/extractos/${detalle.id}/recurrentes`))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudieron crear los recurrentes')
    } finally {
      setCreando(false)
    }
  }

  async function importar() {
    if (!detalle) return
    setImportando(true)
    setError('')
    try {
      const r = await api<ImportarResultado>(`/extractos/${detalle.id}/importar`, {
        method: 'POST',
        body: JSON.stringify({
          cuenta_id: destinoCuenta || null,
          tarjeta_id: destinoTarjeta || null,
          incluir_cuotas_anteriores: incluirAnteriores,
        }),
      })
      setResultado(r)
      await cargar()
      // Se recarga el detalle: los movimientos importados ya traen su transacción
      const [d, p] = await Promise.all([
        api<ExtractoDetalle>(`/extractos/${detalle.id}`),
        api<ImportarPreview>(
          `/extractos/${detalle.id}/importar?incluir_cuotas_anteriores=${incluirAnteriores}`
        ),
      ])
      setDetalle(d)
      setPrevia(p)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo importar')
    } finally {
      setImportando(false)
    }
  }

  async function borrar(id: string) {
    if (!confirm('¿Borrar este extracto y su detalle?')) return
    await api(`/extractos/${id}`, { method: 'DELETE' })
    if (detalle?.id === id) {
      setDetalle(null)
      setAnalisis(null)
    }
    await cargar()
  }

  const visibles = detalle?.movimientos.filter((m) => verInformativos || !m.es_informativo) ?? []
  const usoCupo = pct(analisis?.cupo_utilizado ?? null, analisis?.cupo_total ?? null)

  return (
    <div className="space-y-6 p-4">
      <header>
        <h1 className="text-2xl font-semibold text-slate-800">Extractos</h1>
        <p className="text-sm text-slate-500">
          Sube el extracto de tu tarjeta o de tu cuenta (PDF o Excel). Konta lo lee, dice si los
          números cuadran y te muestra en qué se fue la plata. <strong>Todavía no crea
          transacciones</strong>: eso es el paso siguiente. Si el PDF tiene contraseña, escríbela.
        </p>
      </header>

      <form onSubmit={subir} className="rounded-xl border border-slate-200 bg-white p-4">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          <label className="text-sm sm:col-span-2">
            <span className="text-slate-600">Archivo</span>
            <input
              type="file"
              accept=".pdf,.xlsx,.xlsm,.csv"
              onChange={(e: ChangeEvent<HTMLInputElement>) =>
                setArchivo(e.target.files?.[0] ?? null)
              }
              className="mt-1 block w-full text-sm"
            />
          </label>
          <label className="text-sm">
            <span className="text-slate-600">Contraseña (si la tiene)</span>
            <input
              type="password"
              value={contrasena}
              onChange={(e) => setContrasena(e.target.value)}
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
              placeholder="opcional"
            />
          </label>
          <label className="text-sm">
            <span className="text-slate-600">Tipo</span>
            <select
              value={tipo}
              onChange={(e) => setTipo(e.target.value)}
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
            >
              <option value="tarjeta">Tarjeta de crédito</option>
              <option value="cuenta">Cuenta (ahorros o corriente)</option>
            </select>
          </label>
          <label className="text-sm">
            <span className="text-slate-600">Cuenta o tarjeta</span>
            <div className="mt-1 flex gap-1">
              <select
                value={tipo === 'cuenta' ? cuentaId : tarjetaId}
                onChange={(e) =>
                  tipo === 'cuenta' ? setCuentaId(e.target.value) : setTarjetaId(e.target.value)
                }
                className="w-full rounded-lg border border-slate-300 px-2 py-2 text-sm"
              >
                <option value="">— sin asignar —</option>
                {(tipo === 'cuenta' ? cuentas : tarjetas).map((x) => (
                  <option key={x.id} value={x.id}>
                    {x.nombre}
                  </option>
                ))}
              </select>
            </div>
          </label>
        </div>
        <div className="mt-3 flex items-center gap-3">
          <button
            type="submit"
            disabled={subiendo}
            className="rounded-lg bg-slate-800 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
          >
            {subiendo ? 'Leyendo…' : 'Leer extracto'}
          </button>
          <span className="text-xs text-slate-500">
            El archivo no se guarda: solo se guarda lo que se leyó de él.
          </span>
        </div>
      </form>

      {error && (
        <p className="rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700">
          {error}
        </p>
      )}

      {cargando ? (
        <Cargando />
      ) : (
        <section className="rounded-xl border border-slate-200 bg-white">
          <h2 className="border-b border-slate-100 px-4 py-3 text-sm font-semibold text-slate-700">
            Extractos leídos ({items.length})
          </h2>
          {items.length === 0 ? (
            <p className="p-4 text-sm text-slate-500">
              Todavía no hay ninguno. Sube el primero arriba.
            </p>
          ) : (
            <ul className="divide-y divide-slate-100">
              {items.map((x) => (
                <li key={x.id} className="flex flex-wrap items-center gap-3 px-4 py-3">
                  <button onClick={() => abrir(x.id)} className="text-left">
                    <p className="text-sm font-medium text-slate-800">
                      {x.banco ?? 'Extracto'} · {x.nombre_archivo}
                    </p>
                    <p className="text-xs text-slate-500">
                      {x.tipo === 'cuenta' ? 'Cuenta' : 'Tarjeta'} · {x.formato.toUpperCase()} ·{' '}
                      {x.moneda}
                      {x.periodo_desde && x.periodo_hasta && (
                        <>
                          {' '}
                          · {x.periodo_desde} a {x.periodo_hasta}
                        </>
                      )}
                    </p>
                  </button>
                  <span
                    className={`rounded-full px-2 py-0.5 text-xs ${
                      x.conciliacion_ok
                        ? 'bg-emerald-100 text-emerald-700'
                        : 'bg-amber-100 text-amber-700'
                    }`}
                  >
                    {x.conciliacion_ok ? 'cuadra' : 'revisar'}
                  </span>
                  <span className="ml-auto text-xs text-slate-500">
                    compras {fmtMoney(x.compras)}
                  </span>
                  <button
                    onClick={() => borrar(x.id)}
                    className="text-xs text-rose-600 hover:underline"
                  >
                    borrar
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}

      {detalle && analisis && (
        <section className="space-y-4">
          <div className="flex flex-wrap items-center gap-3">
            <h2 className="text-lg font-semibold text-slate-800">
              {detalle.banco ?? 'Extracto'} · {detalle.nombre_archivo}
            </h2>
            <span
              className={`rounded-full px-2 py-0.5 text-xs ${
                analisis.conciliacion_ok
                  ? 'bg-emerald-100 text-emerald-700'
                  : 'bg-rose-100 text-rose-700'
              }`}
            >
              {analisis.conciliacion_ok ? 'los números cuadran' : 'los números no cuadran'}
            </span>
            <span className="ml-auto text-xs text-slate-500">
              Totales en <strong>{analisis.moneda_extracto}</strong>, la moneda del extracto. El
              detalle en otras monedas va aparte.
            </span>
          </div>

          {analisis.avisos.length > 0 && (
            <ul className="space-y-1 rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
              {analisis.avisos.map((a) => (
                <li key={a}>⚠️ {a}</li>
              ))}
            </ul>
          )}

          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <h3 className="text-sm font-semibold text-slate-700">¿Cuadra con lo que dice el banco?</h3>
            <ul className="mt-2 space-y-1">
              {analisis.conciliacion.map((c) => (
                <Control key={c.nombre} c={c} />
              ))}
            </ul>
            {analisis.conciliacion.some((c) => c.filas_dudosas?.length) && (
              <details className="mt-2 text-xs text-slate-600">
                <summary className="cursor-pointer">Ver los movimientos que no cuadran</summary>
                <ul className="mt-1 space-y-0.5">
                  {analisis.conciliacion
                    .flatMap((c) => c.filas_dudosas ?? [])
                    .map((f, i) => (
                      <li key={i}>
                        {f.fecha} · {f.descripcion} · pendiente {fmtMoney(f.pendiente)} · cuota{' '}
                        {fmtMoney(f.cuota)}
                      </li>
                    ))}
                </ul>
              </details>
            )}
          </div>

          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Tarjeta
              titulo={`Compras del periodo (${analisis.moneda_extracto})`}
              valor={fmtMoney(analisis.compras)}
              detalle={`${analisis.movimientos} movimientos del periodo`}
            />
            <Tarjeta titulo="Pagos y abonos" valor={fmtMoney(analisis.pagos)} tono="bueno" />
            <Tarjeta
              titulo="Costo del dinero"
              valor={fmtMoney(analisis.costos_financieros)}
              detalle={`intereses ${fmtMoney(analisis.intereses)} · comisiones ${fmtMoney(
                analisis.comisiones
              )}`}
              tono={Number(analisis.costos_financieros) > 0 ? 'alerta' : 'normal'}
            />
            <Tarjeta
              titulo="Pago total del corte"
              valor={fmtMoney(analisis.pago_total)}
              detalle={`pago mínimo ${fmtMoney(analisis.pago_minimo)}`}
            />
            {analisis.cupo_total != null && (
              <Tarjeta
                titulo="Cupo utilizado"
                valor={fmtMoney(analisis.cupo_utilizado)}
                detalle={`de ${fmtMoney(analisis.cupo_total)}${
                  usoCupo != null ? ` (${usoCupo}% del cupo)` : ''
                }`}
                tono={usoCupo != null && usoCupo > 70 ? 'alerta' : 'normal'}
              />
            )}
            {analisis.intereses_declarados != null && (
              <Tarjeta
                titulo="Intereses que cobra el banco"
                valor={fmtMoney(analisis.intereses_declarados)}
                detalle="lo que el extracto declara"
                tono="alerta"
              />
            )}
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <div className="rounded-xl border border-slate-200 bg-white p-4">
              <h3 className="text-sm font-semibold text-slate-700">A dónde se fue la plata</h3>
              {analisis.por_categoria.length === 0 ? (
                <p className="mt-2 text-sm text-slate-500">
                  Todavía no hay categorías asignadas. Cuando las haya, aquí aparece el reparto.
                </p>
              ) : (
                <ul className="mt-2 space-y-2">
                  {analisis.por_categoria.map((t) => {
                    const parte = pct(t.total, analisis.compras)
                    return (
                      <li key={t.categoria}>
                        <div className="flex items-baseline justify-between text-sm">
                          <span className="text-slate-700">
                            {t.categoria}
                            {t.etiquetas.length > 0 && (
                              <span className="text-xs text-slate-400"> · {t.etiquetas.join(', ')}</span>
                            )}
                          </span>
                          <span className="text-slate-600">
                            {fmtMoney(t.total)} {parte != null && <span className="text-xs">({parte}%)</span>}
                          </span>
                        </div>
                        <div className="mt-1 h-2 rounded-full bg-slate-100">
                          <div
                            className="h-2 rounded-full bg-slate-700"
                            style={{ width: `${parte ?? 0}%` }}
                          />
                        </div>
                      </li>
                    )
                  })}
                </ul>
              )}
            </div>

            <div className="space-y-4">
              <div className="rounded-xl border border-slate-200 bg-white p-4">
                <h3 className="text-sm font-semibold text-slate-700">Por moneda</h3>
                <table className="mt-2 w-full text-sm">
                  <thead>
                    <tr className="text-left text-xs uppercase text-slate-400">
                      <th className="py-1">Moneda</th>
                      <th className="py-1 text-right">Compras</th>
                      <th className="py-1 text-right">Pagos</th>
                      <th className="py-1 text-right">Pendiente</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(analisis.por_moneda).map(([m, v]) => (
                      <tr key={m} className="border-t border-slate-100">
                        <td className="py-1 font-medium text-slate-700">{m}</td>
                        <td className="py-1 text-right">{fmtMoney(v.compras as string)}</td>
                        <td className="py-1 text-right">{fmtMoney(v.pagos as string)}</td>
                        <td className="py-1 text-right">{fmtMoney(v.pendiente as string)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <p className="mt-2 text-xs text-slate-500">
                  Los movimientos se guardan en su moneda: no se convierten al entrar. El total se
                  muestra en {analisis.moneda}.
                </p>
              </div>

              <div className="rounded-xl border border-slate-200 bg-white p-4">
                <h3 className="text-sm font-semibold text-slate-700">Compromiso futuro</h3>
                <p className="mt-1 text-xs text-slate-500">
                  Lo que ya compraste y todavía vas a pagar en cuotas.
                </p>
                <ul className="mt-2 space-y-1 text-sm">
                  {Object.entries(analisis.compromiso_futuro).length === 0 && (
                    <li className="text-slate-500">Sin compras a cuotas pendientes.</li>
                  )}
                  {Object.entries(analisis.compromiso_futuro).map(([m, v]) => (
                    <li key={m} className="flex justify-between">
                      <span className="text-slate-600">{m}</span>
                      <span className="font-medium text-slate-800">{fmtMoney(v)}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </div>

          {recurrentes.length > 0 && (
            <div className="rounded-xl border border-slate-200 bg-white p-4">
              <h3 className="text-sm font-semibold text-slate-700">
                Recurrentes detectados ({recurrentes.length})
              </h3>
              <p className="mt-1 text-xs text-slate-500">
                Lo que se repite todos los meses. Se detecta por la repetición entre extractos,
                por lo que ya estaba en tus movimientos y por un diccionario de servicios. Una
                compra <strong>a cuotas no es una suscripción</strong>: se queda fuera.
              </p>

              <ul className="mt-3 space-y-2">
                {recurrentes.map((c) => (
                  <li
                    key={c.clave}
                    className={`rounded-lg border p-3 ${
                      c.ya_es_suscripcion ? 'border-emerald-200 bg-emerald-50' : 'border-slate-200'
                    }`}
                  >
                    <div className="flex flex-wrap items-center gap-2">
                      {!c.ya_es_suscripcion ? (
                        <input
                          type="checkbox"
                          checked={Boolean(elegidos[c.clave])}
                          onChange={(e) =>
                            setElegidos((prev) => ({ ...prev, [c.clave]: e.target.checked }))
                          }
                        />
                      ) : (
                        <span className="text-emerald-700">✓</span>
                      )}
                      <span className="text-sm font-medium text-slate-800">{c.nombre}</span>
                      <span
                        className={`rounded-full px-2 py-0.5 text-xs ${
                          c.confianza === 'alta'
                            ? 'bg-emerald-100 text-emerald-700'
                            : c.confianza === 'media'
                              ? 'bg-amber-100 text-amber-700'
                              : 'bg-slate-100 text-slate-600'
                        }`}
                      >
                        {c.confianza}
                      </span>
                      <span className="text-sm text-slate-700">
                        {fmtMoney(c.monto)} <span className="text-xs">{c.moneda}</span> ·{' '}
                        {c.periodicidad}
                      </span>
                      {c.proximo_pago && (
                        <span className="text-xs text-slate-500">
                          próximo {c.proximo_pago}
                        </span>
                      )}
                      {c.ya_es_suscripcion && (
                        <span className="text-xs text-emerald-700">ya está en tus recurrentes</span>
                      )}
                      {!c.en_este_extracto && (
                        <span className="text-xs text-slate-400">de otro extracto</span>
                      )}
                    </div>
                    <ul className="mt-1 pl-6 text-xs text-slate-500">
                      {c.senales.map((s) => (
                        <li key={s}>· {s}</li>
                      ))}
                      {c.fechas.length > 0 && (
                        <li>· cargos: {c.fechas.join(', ')}</li>
                      )}
                    </ul>
                  </li>
                ))}
              </ul>

              <div className="mt-3 flex flex-wrap items-center gap-3">
                <button
                  onClick={crearRecurrentes}
                  disabled={creando || Object.values(elegidos).every((v) => !v)}
                  className="rounded-lg bg-slate-800 px-3 py-2 text-xs font-medium text-white disabled:opacity-50"
                >
                  {creando
                    ? 'Creando…'
                    : `Crear ${Object.values(elegidos).filter(Boolean).length} recurrente(s)`}
                </button>
                <span className="text-xs text-slate-500">
                  Se crean en <strong>Gastos recurrentes</strong>, con su próximo pago calculado.
                </span>
              </div>
              {avisoRecurrentes && (
                <p className="mt-2 rounded-lg bg-emerald-50 p-3 text-xs text-emerald-800">
                  {avisoRecurrentes}
                </p>
              )}
            </div>
          )}

          {previa && (
            <div className="rounded-xl border border-slate-200 bg-white p-4">
              <h3 className="text-sm font-semibold text-slate-700">Importar a Konta</h3>
              <p className="mt-1 text-xs text-slate-500">
                Se importan los movimientos del periodo y se salta lo demás, con su motivo:
                las compras a cuotas entran por la <strong>cuota del mes</strong>, los ajustes
                no entran y lo de meses anteriores tampoco (ya estaba contado).
              </p>

              <ul className="mt-2 space-y-1 text-sm">
                <li className="text-slate-700">
                  ✅ Se importan <strong>{previa.resumen.se_importan}</strong>
                  {Object.entries(previa.resumen.gastos_por_moneda).map(([m, v]) => (
                    <span key={m} className="ml-2 text-slate-500">
                      {m} {fmtMoney(v)}
                    </span>
                  ))}
                </li>
                {Number(previa.resumen.de_meses_anteriores) > 0 && (
                  <li className="text-slate-500">
                    de eso, {fmtMoney(previa.resumen.de_meses_anteriores)} son las cuotas de
                    este mes de compras de meses anteriores
                  </li>
                )}
                {Object.entries(previa.resumen.motivos).map(([motivo, n]) => (
                  <li key={motivo} className="text-slate-500">
                    ➖ {n} · {motivo}
                  </li>
                ))}
              </ul>

              {previa.nota_pago_minimo && (
                <p
                  className={`mt-2 rounded-lg p-3 text-xs ${
                    Number(previa.diferencia_pago_minimo ?? 1) === 0
                      ? 'bg-emerald-50 text-emerald-800'
                      : 'bg-amber-50 text-amber-800'
                  }`}
                >
                  {previa.nota_pago_minimo}
                </p>
              )}

              <label className="mt-3 flex items-start gap-2 text-xs text-slate-600">
                <input
                  type="checkbox"
                  checked={incluirAnteriores}
                  onChange={(e) => {
                    setIncluirAnteriores(e.target.checked)
                    if (detalle) void abrir(detalle.id)
                  }}
                  className="mt-0.5"
                />
                Incluir también las cuotas de este mes de compras de meses anteriores. Es lo
                que estás pagando ahora; si lo desmarcas, el mes no cuadrará con el pago
                mínimo.
              </label>

              <div className="mt-3 flex flex-wrap items-end gap-3">
                <label className="text-xs text-slate-600">
                  Sale de
                  <select
                    value={destinoCuenta}
                    onChange={(e) => setDestinoCuenta(e.target.value)}
                    className="ml-1 rounded border border-slate-300 px-2 py-1 text-xs"
                  >
                    <option value="">— sin cuenta —</option>
                    {cuentas.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.nombre}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="text-xs text-slate-600">
                  Tarjeta
                  <select
                    value={destinoTarjeta}
                    onChange={(e) => setDestinoTarjeta(e.target.value)}
                    className="ml-1 rounded border border-slate-300 px-2 py-1 text-xs"
                  >
                    <option value="">— sin tarjeta —</option>
                    {tarjetas.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.nombre}
                      </option>
                    ))}
                  </select>
                </label>
                <button
                  onClick={importar}
                  disabled={importando || previa.resumen.se_importan === 0}
                  className="rounded-lg bg-slate-800 px-3 py-2 text-xs font-medium text-white disabled:opacity-50"
                >
                  {importando
                    ? 'Importando…'
                    : `Importar ${previa.resumen.se_importan} movimiento(s)`}
                </button>
              </div>

              {previa.resumen.se_importan === 0 && (
                <p className="mt-2 text-xs text-slate-500">
                  No queda nada por importar de este extracto.
                </p>
              )}

              {resultado && (
                <p className="mt-3 rounded-lg bg-emerald-50 p-3 text-sm text-emerald-800">
                  Se crearon <strong>{resultado.creadas}</strong> transacciones.
                  {resultado.deuda_registrada && (
                    <>
                      {' '}
                      Deuda de la tarjeta actualizada con el cupo utilizado del corte (
                      {fmtMoney(resultado.deuda_registrada)}).
                    </>
                  )}
                </p>
              )}
            </div>
          )}

          <div className="rounded-xl border border-slate-200 bg-white">
            <div className="flex flex-wrap items-center gap-3 border-b border-slate-100 px-4 py-3">
              <h3 className="text-sm font-semibold text-slate-700">
                Movimientos ({visibles.length})
              </h3>
              <label className="ml-auto flex items-center gap-2 text-xs text-slate-600">
                <input
                  type="checkbox"
                  checked={verInformativos}
                  onChange={(e) => setVerInformativos(e.target.checked)}
                />
                ver también lo anterior al periodo ({analisis.movimientos_informativos})
              </label>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs uppercase text-slate-400">
                    <th className="px-4 py-2">Fecha</th>
                    <th className="px-4 py-2">Descripción</th>
                    <th className="px-4 py-2">Tipo</th>
                    <th className="px-4 py-2 text-right">Valor</th>
                    <th className="px-4 py-2 text-right">Cuotas</th>
                    <th className="px-4 py-2 text-right">Cuota mes</th>
                    <th className="px-4 py-2 text-right">Pendiente</th>
                  </tr>
                </thead>
                <tbody>
                  {visibles.map((m) => (
                    <tr
                      key={m.id}
                      className={`border-t border-slate-100 ${m.es_informativo ? 'text-slate-400' : ''}`}
                    >
                      <td className="px-4 py-2 whitespace-nowrap">{m.fecha ?? '—'}</td>
                      <td className="px-4 py-2">
                        {m.descripcion || '—'}
                        {m.es_informativo && (
                          <span className="ml-2 rounded bg-slate-100 px-1 text-xs">informativo</span>
                        )}
                        {m.transaccion_id && (
                          <span className="ml-2 rounded bg-emerald-100 px-1 text-xs text-emerald-700">
                            importado
                          </span>
                        )}
                        {m.moneda_original && (
                          <span className="ml-2 text-xs text-slate-400">
                            {fmtMoney(m.monto_original)} {m.moneda_original}
                            {m.tasa_cambio && <> · T.C. {fmtMoney(m.tasa_cambio)}</>}
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-2">
                        <span
                          className={`rounded-full px-2 py-0.5 text-xs ${
                            TIPOS[m.tipo]?.clase ?? 'bg-slate-100 text-slate-600'
                          }`}
                        >
                          {TIPOS[m.tipo]?.label ?? m.tipo}
                        </span>
                      </td>
                      <td
                        className={`px-4 py-2 text-right whitespace-nowrap ${
                          Number(m.valor) < 0 ? 'text-emerald-600' : ''
                        }`}
                      >
                        {fmtMoney(m.valor)} <span className="text-xs text-slate-400">{m.moneda}</span>
                      </td>
                      <td className="px-4 py-2 text-right whitespace-nowrap">
                        {m.cuotas_total ? `${m.cuotas_n}/${m.cuotas_total}` : '—'}
                      </td>
                      <td className="px-4 py-2 text-right whitespace-nowrap">
                        {m.cuota_mes ? fmtMoney(m.cuota_mes) : '—'}
                      </td>
                      <td className="px-4 py-2 text-right whitespace-nowrap">
                        {m.valor_pendiente ? fmtMoney(m.valor_pendiente) : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </section>
      )}
    </div>
  )
}
