import { useEffect, useState } from 'react'
import { api } from '../api'
import { fmtMoney, type PolizaResumen, type ReporteCategoria, type ReporteMes } from '../types'

const ALTO = 160

const TIPO_LABEL: Record<string, string> = {
  vida: 'Vida',
  salud: 'Salud',
  vehiculo: 'Vehículo',
  hogar: 'Hogar',
  otro: 'Otro',
}

export default function Reportes() {
  const [mensual, setMensual] = useState<ReporteMes[]>([])
  const [categorias, setCategorias] = useState<ReporteCategoria[]>([])
  const [seguros, setSeguros] = useState<PolizaResumen | null>(null)
  const [mes, setMes] = useState(new Date().toISOString().slice(0, 7))
  const [error, setError] = useState('')

  useEffect(() => {
    api<ReporteMes[]>('/reportes/mensual?meses=6')
      .then(setMensual)
      .catch((e) => setError(e instanceof Error ? e.message : 'Error'))
    api<PolizaResumen>('/reportes/seguros')
      .then(setSeguros)
      .catch((e) => setError(e instanceof Error ? e.message : 'Error'))
  }, [])

  useEffect(() => {
    api<ReporteCategoria[]>(`/reportes/categorias?mes=${mes}`)
      .then(setCategorias)
      .catch((e) => setError(e instanceof Error ? e.message : 'Error'))
  }, [mes])

  const maxBar = Math.max(...mensual.flatMap((m) => [m.ingresos, m.gastos]), 1)
  const gastos = categorias.filter((c) => c.tipo === 'gasto')
  const ingresos = categorias.filter((c) => c.tipo === 'ingreso')

  return (
    <div>
      <h2 className="text-xl font-semibold">Reportes</h2>
      {error && <p className="mt-2 text-sm text-red-600">{error}</p>}

      <div className="mt-4 rounded-xl border border-slate-200 bg-white p-5">
        <h3 className="font-medium text-slate-700">Ingresos vs Gastos (últimos 6 meses)</h3>
        <div className="mt-4 flex items-end justify-between gap-3">
          {mensual.map((m) => (
            <div key={m.mes} className="flex flex-1 flex-col items-center">
              <div className="flex items-end justify-center gap-1" style={{ height: ALTO }}>
                <div
                  className="w-4 rounded-t bg-emerald-500"
                  style={{ height: `${Math.round((m.ingresos / maxBar) * ALTO)}px` }}
                  title={`Ingresos: ${fmtMoney(m.ingresos)}`}
                />
                <div
                  className="w-4 rounded-t bg-red-500"
                  style={{ height: `${Math.round((m.gastos / maxBar) * ALTO)}px` }}
                  title={`Gastos: ${fmtMoney(m.gastos)}`}
                />
              </div>
              <span className="mt-2 text-xs text-slate-500">{m.mes}</span>
              <span className={`text-xs font-medium ${m.balance >= 0 ? 'text-emerald-600' : 'text-red-600'}`}>
                {m.balance >= 0 ? '+' : ''}{fmtMoney(m.balance)}
              </span>
            </div>
          ))}
        </div>
        <div className="mt-3 flex gap-4 text-xs text-slate-500">
          <span className="flex items-center gap-1"><span className="inline-block h-2 w-2 rounded-full bg-emerald-500" /> Ingresos</span>
          <span className="flex items-center gap-1"><span className="inline-block h-2 w-2 rounded-full bg-red-500" /> Gastos</span>
        </div>
      </div>

      <div className="mt-6 rounded-xl border border-slate-200 bg-white p-5">
        <div className="flex items-center justify-between">
          <h3 className="font-medium text-slate-700">Desglose por categoría</h3>
          <input
            type="month"
            value={mes}
            onChange={(e) => setMes(e.target.value)}
            className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm"
          />
        </div>

        <div className="mt-4 grid gap-6 sm:grid-cols-2">
          <div>
            <h4 className="text-sm font-medium text-red-600">Gastos</h4>
            {gastos.length === 0 ? (
              <p className="mt-2 text-sm text-slate-500">Sin gastos este mes.</p>
            ) : (
              <ul className="mt-2 space-y-2">
                {gastos.map((c) => (
                  <li key={`${c.categoria}-${c.etiqueta ?? ''}`} className="flex items-center justify-between text-sm">
                    <span className="text-slate-700">
                      {c.categoria}
                      {c.etiqueta && <span className="text-slate-400"> › {c.etiqueta}</span>}
                    </span>
                    <span className="font-medium text-slate-900">{fmtMoney(c.total)}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
          <div>
            <h4 className="text-sm font-medium text-emerald-600">Ingresos</h4>
            {ingresos.length === 0 ? (
              <p className="mt-2 text-sm text-slate-500">Sin ingresos este mes.</p>
            ) : (
              <ul className="mt-2 space-y-2">
                {ingresos.map((c) => (
                  <li key={`${c.categoria}-${c.etiqueta ?? ''}`} className="flex items-center justify-between text-sm">
                    <span className="text-slate-700">
                      {c.categoria}
                      {c.etiqueta && <span className="text-slate-400"> › {c.etiqueta}</span>}
                    </span>
                    <span className="font-medium text-slate-900">{fmtMoney(c.total)}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </div>

      {seguros && seguros.polizas_activas > 0 && (
        <div className="mt-6 rounded-xl border border-slate-200 bg-white p-5">
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
              <p className="mt-1 text-xl font-semibold text-slate-800">
                {fmtMoney(seguros.prima_mensual_cop)}
              </p>
            </div>
            <div>
              <p className="text-sm text-slate-500">Al año</p>
              <p className="mt-1 text-xl font-semibold text-slate-800">
                {fmtMoney(seguros.prima_anual_cop)}
              </p>
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
                    <td className="py-2 pr-3 font-medium text-slate-700">
                      {fmtMoney(t.prima_mensual_cop)}
                    </td>
                    <td className="py-2 font-medium text-slate-700">
                      {fmtMoney(t.prima_anual_cop)}
                    </td>
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
