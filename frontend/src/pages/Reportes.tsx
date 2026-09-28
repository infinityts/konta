import { useEffect, useState } from 'react'
import { api } from '../api'
import { fmtMoney, type ReporteCategoria, type ReporteMes } from '../types'

const ALTO = 160

export default function Reportes() {
  const [mensual, setMensual] = useState<ReporteMes[]>([])
  const [categorias, setCategorias] = useState<ReporteCategoria[]>([])
  const [mes, setMes] = useState(new Date().toISOString().slice(0, 7))
  const [error, setError] = useState('')

  useEffect(() => {
    api<ReporteMes[]>('/reportes/mensual?meses=6')
      .then(setMensual)
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
                  <li key={`${c.categoria}-${c.subcategoria ?? ''}`} className="flex items-center justify-between text-sm">
                    <span className="text-slate-700">
                      {c.categoria}
                      {c.subcategoria && <span className="text-slate-400"> › {c.subcategoria}</span>}
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
                  <li key={`${c.categoria}-${c.subcategoria ?? ''}`} className="flex items-center justify-between text-sm">
                    <span className="text-slate-700">
                      {c.categoria}
                      {c.subcategoria && <span className="text-slate-400"> › {c.subcategoria}</span>}
                    </span>
                    <span className="font-medium text-slate-900">{fmtMoney(c.total)}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
