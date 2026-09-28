import { useEffect, useState } from 'react'
import { api } from '../api'
import { fmtMoney, type Simulacion, type Tarjeta } from '../types'

const empty = {
  nombre: '',
  banco: '',
  tipo: 'credito',
  moneda: 'COP',
  dia_corte: '',
  dia_pago: '',
  limite: '',
  tasa_interes: '',
}

export default function Tarjetas() {
  const [items, setItems] = useState<Tarjeta[]>([])
  const [form, setForm] = useState(empty)
  const [show, setShow] = useState(false)
  const [error, setError] = useState('')

  // Simulador
  const [simTarjeta, setSimTarjeta] = useState('')
  const [saldo, setSaldo] = useState('')
  const [pago, setPago] = useState('')
  const [simulacion, setSimulacion] = useState<Simulacion | null>(null)

  async function cargar() {
    try {
      setItems(await api<Tarjeta[]>('/tarjetas'))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Error')
    }
  }

  useEffect(() => {
    cargar()
  }, [])

  async function crear() {
    setError('')
    try {
      await api('/tarjetas', {
        method: 'POST',
        body: JSON.stringify({
          nombre: form.nombre,
          banco: form.banco || null,
          tipo: form.tipo,
          moneda: form.moneda,
          dia_corte: form.dia_corte ? Number(form.dia_corte) : null,
          dia_pago: form.dia_pago ? Number(form.dia_pago) : null,
          limite: form.limite || null,
          tasa_interes: form.tasa_interes || null,
        }),
      })
      setForm(empty)
      setShow(false)
      cargar()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Error al guardar')
    }
  }

  async function eliminar(id: string) {
    await api(`/tarjetas/${id}`, { method: 'DELETE' })
    cargar()
  }

  async function simular() {
    if (!simTarjeta || !saldo) return
    setError('')
    setSimulacion(null)
    try {
      const q = new URLSearchParams({ saldo })
      if (pago) q.set('pago_mensual', pago)
      setSimulacion(await api<Simulacion>(`/tarjetas/${simTarjeta}/simulador?${q.toString()}`))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Error al simular')
    }
  }

  const set = (k: keyof typeof empty, v: string) => setForm((f) => ({ ...f, [k]: v }))

  return (
    <div>
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold">Tarjetas</h2>
        <button onClick={() => setShow((s) => !s)} className="rounded-lg bg-indigo-600 px-3 py-2 text-sm font-medium text-white hover:bg-indigo-700">
          {show ? 'Cancelar' : 'Nueva tarjeta'}
        </button>
      </div>

      {show && (
        <div className="mt-4 grid gap-3 rounded-xl border border-slate-200 bg-white p-4 sm:grid-cols-2">
          <input placeholder="Nombre" value={form.nombre} onChange={(e) => set('nombre', e.target.value)} className="rounded-lg border border-slate-300 px-3 py-2 text-sm" />
          <input placeholder="Banco" value={form.banco} onChange={(e) => set('banco', e.target.value)} className="rounded-lg border border-slate-300 px-3 py-2 text-sm" />
          <select value={form.tipo} onChange={(e) => set('tipo', e.target.value)} className="rounded-lg border border-slate-300 px-3 py-2 text-sm">
            <option value="credito">Crédito</option>
            <option value="debito">Débito</option>
          </select>
          <select value={form.moneda} onChange={(e) => set('moneda', e.target.value)} className="rounded-lg border border-slate-300 px-3 py-2 text-sm">
            <option value="COP">COP</option>
            <option value="USD">USD</option>
            <option value="EUR">EUR</option>
          </select>
          <input type="number" min={1} max={31} placeholder="Día de corte" value={form.dia_corte} onChange={(e) => set('dia_corte', e.target.value)} className="rounded-lg border border-slate-300 px-3 py-2 text-sm" />
          <input type="number" min={1} max={31} placeholder="Día de pago" value={form.dia_pago} onChange={(e) => set('dia_pago', e.target.value)} className="rounded-lg border border-slate-300 px-3 py-2 text-sm" />
          <input placeholder="Límite" value={form.limite} onChange={(e) => set('limite', e.target.value)} className="rounded-lg border border-slate-300 px-3 py-2 text-sm" />
          <input placeholder="Tasa de interés mensual (ej. 0.02)" value={form.tasa_interes} onChange={(e) => set('tasa_interes', e.target.value)} className="rounded-lg border border-slate-300 px-3 py-2 text-sm" />
          <button onClick={crear} className="rounded-lg bg-indigo-600 px-3 py-2 text-sm text-white hover:bg-indigo-700 sm:col-span-2">Guardar</button>
        </div>
      )}

      {error && <p className="mt-3 text-sm text-red-600">{error}</p>}

      <ul className="mt-4 space-y-2">
        {items.map((t) => (
          <li key={t.id} className="flex items-center justify-between rounded-xl border border-slate-200 bg-white p-4">
            <div>
              <p className="font-medium">{t.nombre}{t.banco ? ` · ${t.banco}` : ''}</p>
              <p className="text-sm text-slate-500">
                {t.tipo} · {t.moneda}
                {t.dia_corte ? ` · corte ${t.dia_corte}` : ''}
                {t.dia_pago ? ` · pago ${t.dia_pago}` : ''}
                {t.tasa_interes ? ` · tasa ${t.tasa_interes}` : ''}
              </p>
            </div>
            <div className="flex items-center gap-3">
              <span className="text-sm font-medium">{fmtMoney(t.limite)}</span>
              <button onClick={() => eliminar(t.id)} className="text-sm text-red-600 hover:underline">Eliminar</button>
            </div>
          </li>
        ))}
      </ul>

      {/* Simulador de intereses */}
      <div className="mt-6 rounded-xl border border-slate-200 bg-white p-5">
        <h3 className="font-medium text-slate-700">Simulador de intereses</h3>
        <p className="mt-1 text-sm text-slate-500">
          Calcula cuánto tardas en pagar una deuda y cuánto pagas de intereses. La tasa de la
          tarjeta se interpreta como <strong>tasa mensual</strong>. Si no indicas pago, se usa el 5% del saldo.
        </p>

        <div className="mt-3 flex flex-wrap items-center gap-2">
          <select value={simTarjeta} onChange={(e) => setSimTarjeta(e.target.value)} className="rounded-lg border border-slate-300 px-3 py-2 text-sm">
            <option value="">Elige una tarjeta…</option>
            {items.map((t) => (
              <option key={t.id} value={t.id}>{t.nombre}</option>
            ))}
          </select>
          <input placeholder="Saldo de la deuda" value={saldo} onChange={(e) => setSaldo(e.target.value)} className="w-40 rounded-lg border border-slate-300 px-3 py-2 text-sm" />
          <input placeholder="Pago mensual (opcional)" value={pago} onChange={(e) => setPago(e.target.value)} className="w-48 rounded-lg border border-slate-300 px-3 py-2 text-sm" />
          <button onClick={simular} className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700">Simular</button>
        </div>

        {simulacion && (
          <div className="mt-4">
            {simulacion.viable ? (
              <div className="grid gap-4 sm:grid-cols-3">
                <div className="rounded-xl border border-slate-200 p-4">
                  <p className="text-sm text-slate-500">Meses para pagar</p>
                  <p className="mt-1 text-2xl font-semibold text-slate-900">{simulacion.meses}</p>
                </div>
                <div className="rounded-xl border border-red-200 bg-red-50 p-4">
                  <p className="text-sm text-red-700">Total de intereses</p>
                  <p className="mt-1 text-2xl font-semibold text-red-700">{fmtMoney(simulacion.total_intereses)}</p>
                </div>
                <div className="rounded-xl border border-slate-200 p-4">
                  <p className="text-sm text-slate-500">Total pagado</p>
                  <p className="mt-1 text-2xl font-semibold text-slate-900">{fmtMoney(simulacion.total_pagado)}</p>
                </div>
              </div>
            ) : (
              <p className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                ⚠️ Con un pago de {fmtMoney(simulacion.pago_mensual)} no cubres los intereses
                ({fmtMoney(Number(simulacion.saldo_inicial) * Number(simulacion.tasa_mensual))}/mes): la deuda nunca baja.
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
