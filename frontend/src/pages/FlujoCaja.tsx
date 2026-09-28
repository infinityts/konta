import { useEffect, useState } from 'react'
import { api } from '../api'
import { fmtMoney, type FlujoCaja } from '../types'

export default function FlujoCaja() {
  const [datos, setDatos] = useState<FlujoCaja | null>(null)
  const [meses, setMeses] = useState(6)
  const [error, setError] = useState('')

  useEffect(() => {
    api<FlujoCaja>(`/flujo-caja?meses=${meses}`)
      .then(setDatos)
      .catch((e) => setError(e instanceof Error ? e.message : 'Error'))
  }, [meses])

  return (
    <div>
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold">Proyección de flujo de caja</h2>
        <select value={meses} onChange={(e) => setMeses(Number(e.target.value))} className="rounded-lg border border-slate-300 px-3 py-2 text-sm">
          {[3, 6, 12].map((n) => <option key={n} value={n}>{n} meses</option>)}
        </select>
      </div>
      {error && <p className="mt-2 text-sm text-red-600">{error}</p>}

      {datos && (
        <>
          <div className="mt-4 grid gap-4 sm:grid-cols-4">
            <div className="rounded-xl border border-slate-200 bg-white p-4">
              <p className="text-sm text-slate-500">Ingresos proyectados</p>
              <p className="mt-1 text-xl font-semibold text-emerald-600">{fmtMoney(datos.total_ingresos)}</p>
            </div>
            <div className="rounded-xl border border-slate-200 bg-white p-4">
              <p className="text-sm text-slate-500">Gastos proyectados</p>
              <p className="mt-1 text-xl font-semibold text-red-600">{fmtMoney(datos.total_gastos)}</p>
            </div>
            <div className="rounded-xl border border-slate-200 bg-white p-4">
              <p className="text-sm text-slate-500">Balance final</p>
              <p className={`mt-1 text-xl font-semibold ${datos.balance_final >= 0 ? 'text-emerald-600' : 'text-red-600'}`}>
                {fmtMoney(datos.balance_final)}
              </p>
            </div>
            <div className="rounded-xl border border-slate-200 bg-white p-4">
              <p className="text-sm text-slate-500">Gasto variable / mes</p>
              <p className="mt-1 text-xl font-semibold text-slate-800">{fmtMoney(datos.gasto_variable_promedio)}</p>
            </div>
          </div>

          <div className="mt-6 overflow-x-auto rounded-xl border border-slate-200 bg-white">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-left text-slate-500">
                <tr>
                  <th className="px-4 py-3">Mes</th>
                  <th className="px-4 py-3 text-right">Ingresos</th>
                  <th className="px-4 py-3 text-right">Gastos fijos</th>
                  <th className="px-4 py-3 text-right">Gastos variables</th>
                  <th className="px-4 py-3 text-right">Balance</th>
                  <th className="px-4 py-3 text-right">Acumulado</th>
                </tr>
              </thead>
              <tbody>
                {datos.meses.map((m) => (
                  <tr key={m.mes} className="border-t border-slate-100">
                    <td className="px-4 py-2 font-medium text-slate-700">{m.mes}</td>
                    <td className="px-4 py-2 text-right text-emerald-600">{fmtMoney(m.ingresos)}</td>
                    <td className="px-4 py-2 text-right text-slate-600">{fmtMoney(m.gastos_fijos)}</td>
                    <td className="px-4 py-2 text-right text-slate-600">{fmtMoney(m.gastos_variables)}</td>
                    <td className={`px-4 py-2 text-right font-medium ${m.balance >= 0 ? 'text-emerald-600' : 'text-red-600'}`}>
                      {fmtMoney(m.balance)}
                    </td>
                    <td className={`px-4 py-2 text-right font-medium ${m.acumulado >= 0 ? 'text-slate-800' : 'text-red-600'}`}>
                      {fmtMoney(m.acumulado)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <p className="mt-3 text-xs text-slate-500">
            Proyección basada en tus ingresos recurrentes activos, tus suscripciones activas y el
            promedio de gasto variable de los últimos meses. No incluye gastos únicos futuros.
          </p>
        </>
      )}
    </div>
  )
}
