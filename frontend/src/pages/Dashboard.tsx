import { useEffect, useState } from 'react'
import { api } from '../api'
import { fmtMoney, type Suscripcion, type Tarjeta, type Transaccion } from '../types'

function Kpi({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <p className="text-sm text-slate-500">{label}</p>
      <p className="mt-1 text-xl font-semibold text-slate-900">{value}</p>
    </div>
  )
}

export default function Dashboard() {
  const [transacciones, setTransacciones] = useState<Transaccion[]>([])
  const [suscripciones, setSuscripciones] = useState<Suscripcion[]>([])
  const [tarjetas, setTarjetas] = useState<Tarjeta[]>([])
  const [error, setError] = useState('')

  useEffect(() => {
    Promise.all([
      api<Transaccion[]>('/transacciones'),
      api<Suscripcion[]>('/suscripciones'),
      api<Tarjeta[]>('/tarjetas'),
    ])
      .then(([t, s, ta]) => {
        setTransacciones(t)
        setSuscripciones(s)
        setTarjetas(ta)
      })
      .catch((e) => setError(e instanceof Error ? e.message : 'Error'))
  }, [])

  const now = new Date()
  const mes = now.toISOString().slice(0, 7)
  const mesLabel = now.toLocaleDateString('es-CO', { month: 'long', year: 'numeric' })

  const delMes = transacciones.filter((t) => t.fecha.startsWith(mes))
  const ingresoMes = delMes.filter((t) => t.tipo === 'ingreso').reduce((a, t) => a + Number(t.monto), 0)
  const gastoMes = delMes.filter((t) => t.tipo === 'gasto').reduce((a, t) => a + Number(t.monto), 0)
  const balance = ingresoMes - gastoMes
  const positivo = balance >= 0

  const activas = suscripciones.filter((s) => s.estado === 'activa')
  const costoSubs = activas.reduce((a, s) => a + Number(s.monto), 0)

  return (
    <div>
      <h2 className="text-xl font-semibold">Resumen</h2>
      {error && <p className="mt-2 text-sm text-red-600">{error}</p>}

      {/* Conciliación: ingresos vs gastos */}
      <div
        className={`mt-4 rounded-2xl border p-6 ${
          positivo ? 'border-emerald-200 bg-emerald-50' : 'border-red-200 bg-red-50'
        }`}
      >
        <p className="text-sm font-medium text-slate-600">Balance de {mesLabel}</p>
        <p className={`mt-1 text-3xl font-bold ${positivo ? 'text-emerald-700' : 'text-red-700'}`}>
          {positivo ? '+' : '-'}{fmtMoney(Math.abs(balance))}
        </p>
        <div className="mt-2 flex flex-wrap gap-6 text-sm">
          <span className="font-medium text-emerald-700">Ingresos: {fmtMoney(ingresoMes)}</span>
          <span className="font-medium text-red-700">Gastos: {fmtMoney(gastoMes)}</span>
        </div>
      </div>

      <div className="mt-4 grid gap-4 sm:grid-cols-3">
        <Kpi label="Suscripciones activas" value={`${activas.length} · ${fmtMoney(costoSubs)}`} />
        <Kpi label="Tarjetas" value={String(tarjetas.length)} />
        <Kpi label="Movimientos del mes" value={String(delMes.length)} />
      </div>
    </div>
  )
}
