import { useEffect, useState } from 'react'
import {
  Bar,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { api } from '../api'
import { fmtMoney, type PanelReporte, type PolizaResumen } from '../types'

const TIPO_LABEL: Record<string, string> = {
  vida: 'Vida',
  salud: 'Salud',
  vehiculo: 'Vehículo',
  hogar: 'Hogar',
  otro: 'Otro',
}

const MESES: Record<string, string> = {
  '01': 'Ene', '02': 'Feb', '03': 'Mar', '04': 'Abr', '05': 'May', '06': 'Jun',
  '07': 'Jul', '08': 'Ago', '09': 'Sep', '10': 'Oct', '11': 'Nov', '12': 'Dic',
}

/** `2026-09` -> `Sep 26` */
function mesCorto(mes: string) {
  const [y, m] = mes.split('-')
  return `${MESES[m] ?? m} ${y.slice(2)}`
}

/** Variación vs el mes anterior, en % (o «nuevo» si antes era 0). */
function variacion(actual: number, anterior: number) {
  if (anterior === 0) return { texto: actual > 0 ? 'nuevo' : '—', clase: 'text-slate-400' }
  const pct = ((actual - anterior) / Math.abs(anterior)) * 100
  const signo = pct >= 0 ? '▲' : '▼'
  return {
    texto: `${signo} ${Math.abs(pct).toFixed(0)}%`,
    clase: pct >= 0 ? 'text-emerald-600' : 'text-red-600',
  }
}

function Kpi({ titulo, valor, anterior, color }: { titulo: string; valor: number; anterior?: number; color: string }) {
  const v = variacion(valor, anterior ?? 0)
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <p className="text-xs font-medium uppercase tracking-wide text-slate-500">{titulo}</p>
      <p className={`mt-1 text-2xl font-semibold ${color}`}>{fmtMoney(valor)}</p>
      <p className={`mt-1 text-xs ${v.clase}`}>{v.texto} vs mes anterior</p>
    </div>
  )
}

export default function Reportes() {
  const [panel, setPanel] = useState<PanelReporte | null>(null)
  const [seguros, setSeguros] = useState<PolizaResumen | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    api<PanelReporte>('/reportes/panel?meses=12')
      .then(setPanel)
      .catch((e) => setError(e instanceof Error ? e.message : 'Error'))
    api<PolizaResumen>('/reportes/seguros')
      .then(setSeguros)
      .catch((e) => setError(e instanceof Error ? e.message : 'Error'))
  }, [])

  if (error && !panel) return <div><h2 className="text-xl font-semibold">Reportes</h2><p className="mt-2 text-sm text-red-600">{error}</p></div>
  if (!panel) return <div><h2 className="text-xl font-semibold">Reportes</h2><p className="mt-2 text-sm text-slate-500">Cargando…</p></div>

  const mesAnterior = panel.serie.find((s) => s.mes === panel.anterior)
  const datosSerie = panel.serie.map((s) => ({ ...s, mes: mesCorto(s.mes) }))
  const topCategorias = [...panel.categorias].sort((a, b) => b.total - a.total).slice(0, 8)

  return (
    <div className="pb-10">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold">Reportes</h2>
        <span className="text-sm text-slate-500">{mesCorto(panel.mes)}</span>
      </div>
      {error && <p className="mt-2 text-sm text-red-600">{error}</p>}

      {/* KPIs */}
      <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        <Kpi titulo="Ingresos" valor={panel.kpis.ingresos} anterior={mesAnterior?.ingresos} color="text-emerald-600" />
        <Kpi titulo="Gastos" valor={panel.kpis.gastos} anterior={mesAnterior?.gastos} color="text-red-600" />
        <Kpi titulo="Balance" valor={panel.kpis.balance} anterior={mesAnterior?.balance} color={panel.kpis.balance >= 0 ? 'text-slate-800' : 'text-red-600'} />
        <Kpi titulo="Compras" valor={panel.kpis.compras} anterior={mesAnterior?.compras} color="text-indigo-600" />
        <Kpi titulo="IVA pagado" valor={panel.kpis.iva} anterior={mesAnterior?.iva} color="text-amber-600" />
      </div>

      {/* Gráfica 1: 12 meses */}
      <div className="mt-4 rounded-xl border border-slate-200 bg-white p-5">
        <h3 className="font-medium text-slate-700">Evolución de 12 meses</h3>
        <p className="mt-1 text-sm text-slate-500">Barras: ingresos y gastos · Línea: balance del mes.</p>
        <div className="mt-4 h-64">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={datosSerie} margin={{ top: 5, right: 5, left: 5, bottom: 0 }}>
              <defs>
                <linearGradient id="gIngreso" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#10b981" stopOpacity={0.9} />
                  <stop offset="100%" stopColor="#10b981" stopOpacity={0.5} />
                </linearGradient>
                <linearGradient id="gGasto" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#f43f5e" stopOpacity={0.9} />
                  <stop offset="100%" stopColor="#f43f5e" stopOpacity={0.5} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis dataKey="mes" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`} width={44} />
              <Tooltip formatter={(v) => fmtMoney(Number(v ?? 0))} />
              <Legend />
              <Bar dataKey="ingresos" name="Ingresos" fill="url(#gIngreso)" radius={[3, 3, 0, 0]} />
              <Bar dataKey="gastos" name="Gastos" fill="url(#gGasto)" radius={[3, 3, 0, 0]} />
              <Line dataKey="balance" name="Balance" stroke="#0ea5e9" strokeWidth={2} dot={{ r: 2 }} />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        {/* Gráfica 2: gastos por categoría */}
        <div className="rounded-xl border border-slate-200 bg-white p-5">
          <h3 className="font-medium text-slate-700">Gasto por categoría</h3>
          <div className="mt-4 h-64">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={topCategorias} layout="vertical" margin={{ top: 0, right: 10, left: 10, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" horizontal={false} />
                <XAxis type="number" tick={{ fontSize: 11 }} tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`} />
                <YAxis type="category" dataKey="categoria" tick={{ fontSize: 11 }} width={90} />
                <Tooltip formatter={(v) => fmtMoney(Number(v ?? 0))} />
                <Bar dataKey="total" name="Este mes" fill="#6366f1" radius={[0, 3, 3, 0]} barSize={16} />
                <Bar dataKey="anterior" name="Mes anterior" fill="#c7d2fe" radius={[0, 3, 3, 0]} barSize={16} />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Comparación mes a mes por categoría */}
        <div className="rounded-xl border border-slate-200 bg-white p-5">
          <h3 className="font-medium text-slate-700">Qué subió y qué bajó</h3>
          <ul className="mt-3 space-y-1">
            {panel.categorias.map((c) => {
              const v = variacion(c.total, c.anterior)
              return (
                <li key={c.categoria} className="flex items-center justify-between gap-2 border-b border-slate-100 py-1.5 text-sm">
                  <span className="text-slate-700">{c.categoria}</span>
                  <span className="flex items-center gap-3">
                    <span className="font-medium text-slate-800">{fmtMoney(c.total)}</span>
                    <span className={`w-16 text-right text-xs ${v.clase}`}>{v.texto}</span>
                  </span>
                </li>
              )
            })}
            {panel.categorias.length === 0 && <p className="text-sm text-slate-500">Sin gastos este mes.</p>}
          </ul>
        </div>
      </div>

      {/* Mercado: qué está costando más */}
      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <div className="rounded-xl border border-slate-200 bg-white p-5">
          <h3 className="font-medium text-slate-700">Mercado por etiqueta</h3>
          <p className="mt-1 text-sm text-slate-500">En qué se te fue la plata del mercado este mes.</p>
          <ul className="mt-3 space-y-2">
            {panel.mercado.etiquetas.map((e) => {
              const max = panel.mercado.etiquetas[0]?.total || 1
              const v = variacion(e.total, e.anterior)
              return (
                <li key={e.etiqueta}>
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-slate-700">#{e.etiqueta}</span>
                    <span className="flex items-center gap-2">
                      <span className={`text-xs ${v.clase}`}>{v.texto}</span>
                      <span className="font-medium text-slate-800">{fmtMoney(e.total)}</span>
                    </span>
                  </div>
                  <div className="mt-1 h-1.5 w-full rounded-full bg-slate-100">
                    <div className="h-1.5 rounded-full bg-indigo-500" style={{ width: `${Math.max((e.total / max) * 100, 2)}%` }} />
                  </div>
                </li>
              )
            })}
            {panel.mercado.etiquetas.length === 0 && <p className="text-sm text-slate-500">Sin compras de mercado este mes.</p>}
          </ul>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-5">
          <h3 className="font-medium text-slate-700">Artículos que más te cuestan</h3>
          <ul className="mt-3 divide-y divide-slate-100">
            {panel.mercado.productos.slice(0, 12).map((p) => (
              <li key={p.descripcion} className="flex items-center justify-between gap-2 py-1.5 text-sm">
                <div className="min-w-0">
                  <p className="truncate text-slate-700">{p.descripcion}</p>
                  <p className="text-xs text-slate-400">
                    {p.veces} vez{ p.veces === 1 ? '' : 'es' }
                    {p.precio_promedio != null ? ` · ~${fmtMoney(p.precio_promedio)} c/u` : ''}
                  </p>
                </div>
                <span className="whitespace-nowrap font-medium text-slate-800">{fmtMoney(p.total)}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>

      {/* IVA */}
      <div className="mt-4 grid gap-4 sm:grid-cols-3">
        <div className="rounded-xl border border-slate-200 bg-white p-5">
          <h3 className="text-sm font-medium text-slate-500">IVA del mes</h3>
          <p className="mt-1 text-2xl font-semibold text-amber-600">{fmtMoney(panel.impuestos.mes)}</p>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-5">
          <h3 className="text-sm font-medium text-slate-500">IVA del periodo (12 meses)</h3>
          <p className="mt-1 text-2xl font-semibold text-amber-600">{fmtMoney(panel.impuestos.periodo)}</p>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-5">
          <h3 className="text-sm font-medium text-slate-500">Sobre las compras</h3>
          <p className="mt-1 text-2xl font-semibold text-slate-800">
            {panel.impuestos.sobre_compras != null ? `${panel.impuestos.sobre_compras}%` : 'sin dato'}
          </p>
        </div>
      </div>

      {/* Seguros */}
      {seguros && seguros.polizas_activas > 0 && (
        <div className="mt-4 rounded-xl border border-slate-200 bg-white p-5">
          <h3 className="font-medium text-slate-700">Costo de los seguros</h3>
          <p className="mt-1 text-sm text-slate-500">
            Primas de las pólizas activas, normalizadas a COP (una prima anual pesa 1/12 al mes,
            una semestral 1/6).
          </p>

          <div className="mt-4 grid gap-4 sm:grid-cols-3">
            <div>
              <p className="text-sm text-slate-500">Pólizas activas</p>
              <p className="mt-1 text-xl font-semibold text-slate-800">{seguros.polizas_activas}</p>
            </div>
            <div>
              <p className="text-sm text-slate-500">Al mes</p>
              <p className="mt-1 text-xl font-semibold text-slate-800">{fmtMoney(seguros.prima_mensual_cop)}</p>
            </div>
            <div>
              <p className="text-sm text-slate-500">Al año</p>
              <p className="mt-1 text-xl font-semibold text-slate-800">{fmtMoney(seguros.prima_anual_cop)}</p>
            </div>
          </div>

          {seguros.por_tipo.length > 0 && (
            <table className="mt-4 w-full text-sm">
              <thead>
                <tr className="text-left text-xs uppercase tracking-wide text-slate-500">
                  <th className="py-1 pr-3">Tipo</th>
                  <th className="py-1 pr-3">Pólizas</th>
                  <th className="py-1 pr-3">Al mes</th>
                  <th className="py-1">Al año</th>
                </tr>
              </thead>
              <tbody>
                {seguros.por_tipo.map((t) => (
                  <tr key={t.tipo} className="border-t border-slate-200">
                    <td className="py-2 pr-3 text-slate-700">{TIPO_LABEL[t.tipo] ?? t.tipo}</td>
                    <td className="py-2 pr-3 text-slate-600">{t.polizas}</td>
                    <td className="py-2 pr-3 font-medium text-slate-700">{fmtMoney(t.prima_mensual_cop)}</td>
                    <td className="py-2 font-medium text-slate-700">{fmtMoney(t.prima_anual_cop)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          {seguros.sin_tasa.length > 0 && (
            <p className="mt-3 rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-700">
              Sin tasa de cambio para <strong>{seguros.sin_tasa.join(', ')}</strong>: esas primas no
              se incluyen en el total. Regístrala en <em>Monedas</em>.
            </p>
          )}
        </div>
      )}
    </div>
  )
}
