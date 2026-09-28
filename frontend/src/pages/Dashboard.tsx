import { useEffect, useState } from 'react'
import { api } from '../api'
import {
  fmtMoney,
  type Alerta,
  type Categoria,
  type Diagnostico,
  type Suscripcion,
  type Tarjeta,
  type Transaccion,
} from '../types'

function Kpi({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <p className="text-sm text-slate-500">{label}</p>
      <p className="mt-1 text-xl font-semibold text-slate-900">{value}</p>
    </div>
  )
}

const ETIQUETA_ALERTA: Record<string, string> = {
  suscripcion: 'suscripción',
  tarjeta_pago: 'pago tarjeta',
  tarjeta_corte: 'corte tarjeta',
}

export default function Dashboard() {
  const [transacciones, setTransacciones] = useState<Transaccion[]>([])
  const [suscripciones, setSuscripciones] = useState<Suscripcion[]>([])
  const [tarjetas, setTarjetas] = useState<Tarjeta[]>([])
  const [categorias, setCategorias] = useState<Categoria[]>([])
  const [alertas, setAlertas] = useState<Alerta[]>([])
  const [diag, setDiag] = useState<Diagnostico | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    Promise.all([
      api<Transaccion[]>('/transacciones'),
      api<Suscripcion[]>('/suscripciones'),
      api<Tarjeta[]>('/tarjetas'),
      api<Categoria[]>('/categorias'),
      api<Alerta[]>('/alertas?dias=15'),
      api<Diagnostico>('/saldos/diagnostico'),
    ])
      .then(([t, s, ta, c, al, d]) => {
        setTransacciones(t)
        setSuscripciones(s)
        setTarjetas(ta)
        setCategorias(c)
        setAlertas(al)
        setDiag(d)
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

  // "Categoría › Subcategoría" cuando la categoría tiene padre
  const etiquetaCategoria = (id: string | null): string => {
    if (!id) return 'Sin categoría'
    const c = categorias.find((x) => x.id === id)
    if (!c) return 'Sin categoría'
    if (c.padre_id) {
      const padre = categorias.find((x) => x.id === c.padre_id)
      if (padre) return `${padre.nombre} › ${c.nombre}`
    }
    return c.nombre
  }

  const porCategoria = new Map<string, number>()
  for (const t of delMes) {
    if (t.tipo !== 'gasto') continue
    const key = etiquetaCategoria(t.categoria_id)
    porCategoria.set(key, (porCategoria.get(key) ?? 0) + Number(t.monto))
  }
  const topCategorias = [...porCategoria.entries()]
    .map(([nombre, total]) => ({ nombre, total }))
    .sort((a, b) => b.total - a.total)
    .slice(0, 6)
  const maxTop = topCategorias[0]?.total ?? 0

  return (
    <div>
      <h2 className="text-xl font-semibold">Resumen</h2>
      {error && <p className="mt-2 text-sm text-red-600">{error}</p>}

      {/* Saldo real y el motivo */}
      {diag && (
        <div
          className={`mt-4 rounded-2xl border p-6 ${
            diag.sobregirado ? 'border-red-300 bg-red-50' : 'border-emerald-200 bg-emerald-50'
          }`}
        >
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <p className="text-sm font-medium text-slate-600">
              Saldo actual {diag.sobregirado && <span className="font-bold text-red-700">· SOBREGIRADO</span>}
            </p>
            <a href="/cuentas" className="text-xs text-slate-500 underline">ver cuentas</a>
          </div>
          <p className={`mt-1 text-4xl font-bold ${diag.sobregirado ? 'text-red-700' : 'text-emerald-700'}`}>
            {fmtMoney(diag.saldo_actual)}
          </p>
          <ul className="mt-3 space-y-1 text-sm">
            {diag.motivos.map((m, i) => (
              <li key={i} className={diag.sobregirado ? 'text-red-700' : 'text-slate-600'}>
                • {m}
              </li>
            ))}
          </ul>
        </div>
      )}

      <div
        className={`mt-4 rounded-2xl border p-6 ${
          positivo ? 'border-slate-200 bg-white' : 'border-amber-200 bg-amber-50'
        }`}
      >
        <p className="text-sm font-medium text-slate-600">Balance de {mesLabel}</p>
        <p className={`mt-1 text-3xl font-bold ${positivo ? 'text-slate-900' : 'text-amber-700'}`}>
          {positivo ? '+' : '-'}{fmtMoney(Math.abs(balance))}
        </p>
        <div className="mt-2 flex flex-wrap gap-6 text-sm">
          <span className="font-medium text-emerald-700">Ingresos: {fmtMoney(ingresoMes)}</span>
          <span className="font-medium text-red-700">Gastos: {fmtMoney(gastoMes)}</span>
        </div>
      </div>

      <div className="mt-6 rounded-xl border border-slate-200 bg-white p-5">
        <h3 className="font-medium text-slate-700">🔔 Próximos pagos (15 días)</h3>
        {alertas.length === 0 ? (
          <p className="mt-2 text-sm text-slate-500">Sin pagos próximos.</p>
        ) : (
          <ul className="mt-3 divide-y divide-slate-100">
            {alertas.map((a, i) => (
              <li key={i} className="flex items-center justify-between py-2 text-sm">
                <span className="text-slate-700">
                  {a.titulo}
                  <span className="ml-2 text-xs text-slate-400">{ETIQUETA_ALERTA[a.tipo] ?? a.tipo}</span>
                  {a.monto != null && <span className="ml-2 text-xs text-slate-500">{fmtMoney(a.monto)}</span>}
                </span>
                <span
                  className={
                    a.dias_restantes <= 0
                      ? 'font-medium text-red-600'
                      : a.dias_restantes <= 3
                        ? 'font-medium text-amber-600'
                        : 'text-slate-500'
                  }
                >
                  {a.fecha} · {a.dias_restantes <= 0 ? 'vencido' : `en ${a.dias_restantes}d`}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="mt-4 grid gap-4 sm:grid-cols-3">
        <Kpi label="Suscripciones activas" value={`${activas.length} · ${fmtMoney(costoSubs)}`} />
        <Kpi label="Tarjetas" value={String(tarjetas.length)} />
        <Kpi label="Movimientos del mes" value={String(delMes.length)} />
      </div>

      <div className="mt-6 rounded-xl border border-slate-200 bg-white p-5">
        <h3 className="font-medium text-slate-700">Top categorías del mes (gastos)</h3>
        {topCategorias.length === 0 ? (
          <p className="mt-2 text-sm text-slate-500">Aún no hay gastos este mes.</p>
        ) : (
          <ul className="mt-4 space-y-3">
            {topCategorias.map((c) => (
              <li key={c.nombre}>
                <div className="flex justify-between text-sm">
                  <span className="text-slate-700">{c.nombre}</span>
                  <span className="font-medium text-slate-900">{fmtMoney(c.total)}</span>
                </div>
                <div className="mt-1 h-2 w-full rounded-full bg-slate-100">
                  <div
                    className="h-2 rounded-full bg-indigo-500"
                    style={{ width: `${maxTop ? Math.round((c.total / maxTop) * 100) : 0}%` }}
                  />
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}
