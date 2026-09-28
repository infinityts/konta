import { useEffect, useState } from 'react'
import { api } from '../api'
import { fmtMoney, type Suscripcion, type Tarjeta, type Transaccion } from '../types'

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

  const mes = new Date().toISOString().slice(0, 7)
  const delMes = transacciones.filter((t) => t.fecha.startsWith(mes))
  const gastoMes = delMes.filter((t) => t.tipo === 'gasto').reduce((a, t) => a + Number(t.monto), 0)
  const ingresoMes = delMes.filter((t) => t.tipo === 'ingreso').reduce((a, t) => a + Number(t.monto), 0)
  const activas = suscripciones.filter((s) => s.estado === 'activa')
  const costoSubs = activas.reduce((a, s) => a + Number(s.monto), 0)

  const kpis = [
    { label: 'Gasto del mes', value: fmtMoney(gastoMes), color: 'text-red-600' },
    { label: 'Ingresos del mes', value: fmtMoney(ingresoMes), color: 'text-emerald-600' },
    { label: 'Suscripciones activas', value: `${activas.length} · ${fmtMoney(costoSubs)}`, color: 'text-indigo-600' },
    { label: 'Tarjetas', value: String(tarjetas.length), color: 'text-slate-900' },
  ]

  return (
    <div>
      <h2 className="text-xl font-semibold">Resumen</h2>
      {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
      <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {kpis.map((k) => (
          <div key={k.label} className="rounded-xl border border-slate-200 bg-white p-4">
            <p className="text-sm text-slate-500">{k.label}</p>
            <p className={`mt-1 text-2xl font-semibold ${k.color}`}>{k.value}</p>
          </div>
        ))}
      </div>
    </div>
  )
}
