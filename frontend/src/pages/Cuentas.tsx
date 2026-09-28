import { useEffect, useState } from 'react'
import { api } from '../api'
import { fmtMoney, type Consolidado, type SaldoResumen } from '../types'

const TIPOS = ['efectivo', 'banco', 'ahorro', 'otro']

export default function Cuentas() {
  const [resumen, setResumen] = useState<SaldoResumen | null>(null)
  const [consolidado, setConsolidado] = useState<Consolidado | null>(null)
  const [meses, setMeses] = useState(6)
  const [form, setForm] = useState({ nombre: '', tipo: 'efectivo', saldo_inicial: '' })
  const [edicion, setEdicion] = useState<Record<string, string>>({})
  const [show, setShow] = useState(false)
  const [mensaje, setMensaje] = useState('')
  const [error, setError] = useState('')

  async function cargar() {
    try {
      setResumen(await api<SaldoResumen>('/cuentas'))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Error')
    }
  }

  useEffect(() => {
    cargar()
  }, [])

  useEffect(() => {
    api<Consolidado>(`/saldos/consolidado?meses=${meses}`)
      .then(setConsolidado)
      .catch((e) => setError(e instanceof Error ? e.message : 'Error'))
  }, [meses])

  async function crear() {
    setError('')
    try {
      await api('/cuentas', {
        method: 'POST',
        body: JSON.stringify({
          nombre: form.nombre,
          tipo: form.tipo,
          saldo_inicial: form.saldo_inicial || '0',
        }),
      })
      setForm({ nombre: '', tipo: 'efectivo', saldo_inicial: '' })
      setShow(false)
      cargar()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Error al guardar')
    }
  }

  async function guardarSaldo(id: string) {
    const valor = edicion[id]
    if (valor === undefined) return
    await api(`/cuentas/${id}`, { method: 'PATCH', body: JSON.stringify({ saldo_inicial: valor || '0' }) })
    setEdicion((e) => {
      const copia = { ...e }
      delete copia[id]
      return copia
    })
    cargar()
  }

  async function eliminar(id: string) {
    await api(`/cuentas/${id}`, { method: 'DELETE' })
    cargar()
  }

  async function adoptar(id: string) {
    setError('')
    setMensaje('')
    try {
      const r = await api<{ asignados: number }>(`/cuentas/${id}/adoptar-movimientos`, { method: 'POST' })
      setMensaje(`✅ ${r.asignados} movimiento(s) asignados a la cuenta.`)
      cargar()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Error al asignar los movimientos')
    }
  }

  return (
    <div>
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold">Cuentas y saldo</h2>
        <button onClick={() => setShow((s) => !s)} className="rounded-lg bg-indigo-600 px-3 py-2 text-sm font-medium text-white hover:bg-indigo-700">
          {show ? 'Cancelar' : 'Nueva cuenta'}
        </button>
      </div>
      {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
      {mensaje && <p className="mt-2 text-sm text-emerald-700">{mensaje}</p>}

      {resumen && resumen.sin_cuenta_movimientos > 0 && resumen.cuentas.length > 0 && (
        <p className="mt-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
          Tienes <strong>{resumen.sin_cuenta_movimientos}</strong> movimiento(s) sin cuenta
          ({fmtMoney(resumen.sin_cuenta)}). Usa <em>«Asignar movimientos»</em> en la cuenta correcta
          para que el saldo cuadre.
        </p>
      )}

      {resumen && (
        <div className={`mt-4 rounded-2xl border p-6 ${resumen.sobregirado ? 'border-red-300 bg-red-50' : 'border-emerald-200 bg-emerald-50'}`}>
          <p className="text-sm font-medium text-slate-600">
            Saldo total {resumen.sobregirado && <span className="font-bold text-red-700">· SOBREGIRADO</span>}
          </p>
          <p className={`mt-1 text-4xl font-bold ${resumen.sobregirado ? 'text-red-700' : 'text-emerald-700'}`}>
            {fmtMoney(resumen.saldo_total)}
          </p>
          <div className="mt-2 flex flex-wrap gap-6 text-sm text-slate-600">
            <span>Saldo inicial: <strong>{fmtMoney(resumen.saldo_inicial_total)}</strong></span>
            <span className="text-emerald-700">+ Ingresos: <strong>{fmtMoney(resumen.ingresos_total)}</strong></span>
            <span className="text-red-700">− Gastos: <strong>{fmtMoney(resumen.gastos_total)}</strong></span>
            {resumen.sin_cuenta !== 0 && <span className="text-amber-700">Sin cuenta: <strong>{fmtMoney(resumen.sin_cuenta)}</strong></span>}
          </div>
        </div>
      )}

      {show && (
        <div className="mt-4 grid gap-3 rounded-xl border border-slate-200 bg-white p-4 sm:grid-cols-4">
          <input placeholder="Nombre (ej. Banco Bogotá)" value={form.nombre} onChange={(e) => setForm((f) => ({ ...f, nombre: e.target.value }))} className="rounded-lg border border-slate-300 px-3 py-2 text-sm" />
          <select value={form.tipo} onChange={(e) => setForm((f) => ({ ...f, tipo: e.target.value }))} className="rounded-lg border border-slate-300 px-3 py-2 text-sm">
            {TIPOS.map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
          <input placeholder="Saldo inicial" value={form.saldo_inicial} onChange={(e) => setForm((f) => ({ ...f, saldo_inicial: e.target.value }))} className="rounded-lg border border-slate-300 px-3 py-2 text-sm" />
          <button onClick={crear} className="rounded-lg bg-indigo-600 px-3 py-2 text-sm text-white hover:bg-indigo-700">Guardar</button>
        </div>
      )}

      <ul className="mt-4 space-y-3">
        {resumen?.cuentas.map((c) => (
          <li key={c.id} className="rounded-xl border border-slate-200 bg-white p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <span className="font-medium">{c.nombre}</span>
                <span className="ml-2 rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600">{c.tipo}</span>
              </div>
              <div className="flex items-center gap-4">
                <span className={`text-lg font-semibold ${c.saldo_actual < 0 ? 'text-red-600' : 'text-slate-900'}`}>
                  {fmtMoney(c.saldo_actual)}
                </span>
                <button onClick={() => eliminar(c.id)} className="text-sm text-red-600 hover:underline">Eliminar</button>
              </div>
            </div>
            <div className="mt-2 flex flex-wrap items-center gap-4 text-sm text-slate-500">
              <span className="flex items-center gap-2">
                Saldo inicial:
                <input
                  value={edicion[c.id] ?? String(c.saldo_inicial)}
                  onChange={(e) => setEdicion((x) => ({ ...x, [c.id]: e.target.value }))}
                  className="w-28 rounded-lg border border-slate-300 px-2 py-1 text-sm"
                />
                {edicion[c.id] !== undefined && (
                  <button onClick={() => guardarSaldo(c.id)} className="text-xs text-indigo-600 hover:underline">guardar</button>
                )}
              </span>
              <span className="text-emerald-700">+ {fmtMoney(c.ingresos)}</span>
              <span className="text-red-700">− {fmtMoney(c.gastos)}</span>
              {(c.transferencias_enviadas ?? 0) > 0 && (
                <span className="text-slate-500" title="Transferencias enviadas a otra cuenta">
                  − {fmtMoney(c.transferencias_enviadas)} (transferencia)
                </span>
              )}
              {(c.transferencias_recibidas ?? 0) > 0 && (
                <span className="text-slate-500" title="Transferencias recibidas de otra cuenta">
                  + {fmtMoney(c.transferencias_recibidas)} (transferencia)
                </span>
              )}
              {resumen.sin_cuenta_movimientos > 0 && (
                <button onClick={() => adoptar(c.id)} className="text-xs text-indigo-600 hover:underline">
                  Asignar {resumen.sin_cuenta_movimientos} movimiento(s) sin cuenta
                </button>
              )}
            </div>
          </li>
        ))}
        {resumen?.cuentas.length === 0 && (
          <li className="rounded-xl border border-dashed border-slate-300 p-4 text-sm text-slate-500">
            Aún no tienes cuentas. Crea una con tu saldo inicial para que la app sepa cuánto tienes.
          </li>
        )}
      </ul>

      {/* Consolidado mes a mes */}
      <div className="mt-6 rounded-xl border border-slate-200 bg-white p-5">
        <div className="flex items-center justify-between">
          <h3 className="font-medium text-slate-700">Consolidado mes a mes</h3>
          <select value={meses} onChange={(e) => setMeses(Number(e.target.value))} className="rounded-lg border border-slate-300 px-3 py-2 text-sm">
            {[3, 6, 12].map((n) => <option key={n} value={n}>{n} meses</option>)}
          </select>
        </div>
        {consolidado && (
          <div className="mt-3 overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-left text-slate-500">
                <tr>
                  <th className="px-3 py-2">Mes</th>
                  <th className="px-3 py-2 text-right">Saldo inicial</th>
                  <th className="px-3 py-2 text-right">Ingresos</th>
                  <th className="px-3 py-2 text-right">Gastos</th>
                  <th className="px-3 py-2 text-right">Balance</th>
                  <th className="px-3 py-2 text-right">Saldo final</th>
                </tr>
              </thead>
              <tbody>
                {consolidado.meses.map((m) => (
                  <tr key={m.mes} className="border-t border-slate-100">
                    <td className="px-3 py-2 font-medium text-slate-700">{m.mes}</td>
                    <td className="px-3 py-2 text-right text-slate-600">{fmtMoney(m.saldo_inicial)}</td>
                    <td className="px-3 py-2 text-right text-emerald-600">{fmtMoney(m.ingresos)}</td>
                    <td className="px-3 py-2 text-right text-red-600">{fmtMoney(m.gastos)}</td>
                    <td className={`px-3 py-2 text-right font-medium ${m.balance >= 0 ? 'text-emerald-600' : 'text-red-600'}`}>{fmtMoney(m.balance)}</td>
                    <td className={`px-3 py-2 text-right font-semibold ${m.saldo_final < 0 ? 'text-red-600' : 'text-slate-900'}`}>{fmtMoney(m.saldo_final)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
