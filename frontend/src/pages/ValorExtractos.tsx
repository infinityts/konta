import { useEffect, useState } from 'react'
import { api } from '../api'
import { Cargando } from '../components/loading-ui/cargando'
import {
  fmtMoney,
  type Extracto,
  type CostosDelDinero,
  type Hallazgo,
  type Proyeccion,
  type SimulacionExtracto,
} from '../types'

/**
 * Valor acumulado de los extractos (Fase 4).
 *
 * Tres preguntas: cuánto debo y cuánto me toca cada mes, cuánto me está costando esa deuda
 * y si lo que dice el banco cuadra con lo que tengo registrado.
 */
export default function ValorExtractos() {
  const [proyeccion, setProyeccion] = useState<Proyeccion | null>(null)
  const [costos, setCostos] = useState<CostosDelDinero | null>(null)
  const [extractos, setExtractos] = useState<Extracto[]>([])
  const [simulacion, setSimulacion] = useState<SimulacionExtracto | null>(null)
  const [auditorias, setAuditorias] = useState<Record<string, Hallazgo[]>>({})
  const [meses, setMeses] = useState(12)
  const [pago, setPago] = useState('')
  const [cargando, setCargando] = useState(true)

  useEffect(() => {
    Promise.all([
      api<Proyeccion>(`/extractos/proyeccion?meses=${meses}`).then(setProyeccion),
      api<CostosDelDinero>('/extractos/costos').then(setCostos),
      api<Extracto[]>('/extractos').then(setExtractos),
      api<SimulacionExtracto>('/extractos/simulador').then(setSimulacion),
    ]).finally(() => setCargando(false))
  }, [meses])

  async function simular(pagoMensual: string) {
    const extra = pagoMensual ? `&pago_mensual=${pagoMensual}` : ''
    setSimulacion(await api<SimulacionExtracto>(`/extractos/simulador?_=1${extra}`))
  }

  async function auditar(id: string) {
    const hallazgos = await api<Hallazgo[]>(`/extractos/${id}/auditoria`)
    setAuditorias((prev) => ({ ...prev, [id]: hallazgos }))
  }

  if (cargando) return <Cargando />

  const monedas = Object.keys(proyeccion?.por_moneda ?? {})
  const maxMes = Math.max(
    1,
    ...monedas.flatMap((m) =>
      Object.values(proyeccion!.por_moneda[m].meses).map((v) => Number(v))
    )
  )

  return (
    <div className="space-y-6 p-4">
      <header>
        <h1 className="text-2xl font-semibold text-slate-800">Deuda y cuotas</h1>
        <p className="text-sm text-slate-500">
          Lo que ya compraste y todavía vas a pagar, cuánto te está costando esa deuda y si lo que
          dice el banco cuadra con lo que tienes registrado en Konta.
        </p>
      </header>

      {monedas.length === 0 ? (
        <p className="rounded-xl border border-slate-200 bg-white p-4 text-sm text-slate-500">
          Todavía no hay compras a cuotas pendientes. Sube un extracto en{' '}
          <strong>Extractos</strong> y vuelve por aquí.
        </p>
      ) : (
        <section className="space-y-3">
          <div className="flex flex-wrap items-center gap-3">
            <h2 className="text-lg font-semibold text-slate-700">Compromiso futuro</h2>
            <label className="ml-auto text-xs text-slate-500">
              Ver{' '}
              <select
                value={meses}
                onChange={(e) => setMeses(Number(e.target.value))}
                className="rounded border border-slate-300 px-1 py-0.5 text-xs"
              >
                <option value={6}>6 meses</option>
                <option value={12}>12 meses</option>
                <option value={24}>24 meses</option>
              </select>
            </label>
          </div>

          {monedas.map((m) => {
            const d = proyeccion!.por_moneda[m]
            return (
              <div key={m} className="rounded-xl border border-slate-200 bg-white p-4">
                <div className="flex flex-wrap items-baseline gap-4">
                  <div>
                    <p className="text-xs uppercase text-slate-500">Capital pendiente ({m})</p>
                    <p className="text-xl font-semibold text-slate-800">{fmtMoney(d.pendiente)}</p>
                  </div>
                  <div>
                    <p className="text-xs uppercase text-slate-500">Cuota mensual actual</p>
                    <p className="text-xl font-semibold text-slate-800">
                      {fmtMoney(d.cuota_mensual_actual)}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs uppercase text-slate-500">Compras a cuotas</p>
                    <p className="text-xl font-semibold text-slate-800">{d.compras}</p>
                  </div>
                </div>

                <div className="mt-4 space-y-1">
                  {Object.entries(d.meses).map(([mes, valor]) => (
                    <div key={mes} className="flex items-center gap-2 text-xs">
                      <span className="w-16 text-slate-500">{mes}</span>
                      <div className="h-3 flex-1 rounded-full bg-slate-100">
                        <div
                          className="h-3 rounded-full bg-slate-700"
                          style={{ width: `${(Number(valor) / maxMes) * 100}%` }}
                        />
                      </div>
                      <span className="w-24 text-right text-slate-600">{fmtMoney(valor)}</span>
                    </div>
                  ))}
                </div>
                <p className="mt-2 text-xs text-slate-500">
                  Los meses empiezan después del corte del {proyeccion!.desde}. Cada moneda va por
                  separado: no se convierte.
                </p>
              </div>
            )
          })}

          <div className="rounded-xl border border-slate-200 bg-white">
            <h3 className="border-b border-slate-100 px-4 py-3 text-sm font-semibold text-slate-700">
              Compra por compra
            </h3>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs uppercase text-slate-400">
                    <th className="px-4 py-2">Compra</th>
                    <th className="px-4 py-2 text-right">Valor</th>
                    <th className="px-4 py-2 text-right">Cuota</th>
                    <th className="px-4 py-2 text-right">Va en</th>
                    <th className="px-4 py-2 text-right">Faltan</th>
                    <th className="px-4 py-2 text-right">Pendiente</th>
                    <th className="px-4 py-2 text-right">Tasa E.A.</th>
                  </tr>
                </thead>
                <tbody>
                  {proyeccion!.detalle.map((c, i) => (
                    <tr key={i} className="border-t border-slate-100">
                      <td className="px-4 py-2">{c.descripcion || '(sin descripción)'}</td>
                      <td className="px-4 py-2 text-right">{fmtMoney(c.valor_compra)}</td>
                      <td className="px-4 py-2 text-right">{fmtMoney(c.cuota_mes)}</td>
                      <td className="px-4 py-2 text-right">{c.cuotas}</td>
                      <td className="px-4 py-2 text-right">{c.cuotas_restantes}</td>
                      <td className="px-4 py-2 text-right">{fmtMoney(c.pendiente)}</td>
                      <td className="px-4 py-2 text-right">
                        {c.tasa_ea ? `${(Number(c.tasa_ea) * 100).toFixed(2)} %` : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </section>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        <section className="rounded-xl border border-slate-200 bg-white p-4">
          <h2 className="text-lg font-semibold text-slate-700">Costo del dinero</h2>
          <p className="text-xs text-slate-500">
            Intereses, comisiones e impuestos. Es lo que te cuesta deber.
          </p>
          {Object.entries(costos?.total_por_moneda ?? {}).length === 0 ? (
            <p className="mt-2 text-sm text-slate-500">Sin extractos leídos todavía.</p>
          ) : (
            <>
              <div className="mt-2 flex flex-wrap gap-4">
                {Object.entries(costos!.total_por_moneda).map(([m, v]) => (
                  <div key={m}>
                    <p className="text-xs uppercase text-slate-500">Total {m}</p>
                    <p className="text-xl font-semibold text-rose-600">{fmtMoney(v)}</p>
                  </div>
                ))}
              </div>
              <table className="mt-3 w-full text-sm">
                <thead>
                  <tr className="text-left text-xs uppercase text-slate-400">
                    <th className="py-1">Extracto</th>
                    <th className="py-1 text-right">Intereses</th>
                    <th className="py-1 text-right">Comisiones</th>
                    <th className="py-1 text-right">Costo</th>
                    <th className="py-1 text-right">Del pago</th>
                  </tr>
                </thead>
                <tbody>
                  {costos!.extractos.map((c) => (
                    <tr key={c.extracto_id} className="border-t border-slate-100">
                      <td className="py-1">
                        {c.banco ?? 'Extracto'}
                        <span className="ml-1 text-xs text-slate-400">
                          {c.fecha_corte ?? ''}
                        </span>
                      </td>
                      <td className="py-1 text-right">{fmtMoney(c.intereses)}</td>
                      <td className="py-1 text-right">{fmtMoney(c.comisiones)}</td>
                      <td className="py-1 text-right font-medium">{fmtMoney(c.costo)}</td>
                      <td className="py-1 text-right">
                        {c.porcentaje_del_pago != null ? `${c.porcentaje_del_pago} %` : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}
        </section>

        <section className="rounded-xl border border-slate-200 bg-white p-4">
          <h2 className="text-lg font-semibold text-slate-700">Simulador con la tasa real</h2>
          {simulacion?.aviso ? (
            <p className="mt-2 rounded-lg bg-amber-50 p-3 text-sm text-amber-800">
              {simulacion.aviso}
            </p>
          ) : (
            simulacion && (
              <>
                <p className="mt-1 text-xs text-slate-500">
                  Tasa <strong>{(Number(simulacion.tasa_ea) * 100).toFixed(2)} % E.A.</strong> (
                  {simulacion.fuente_de_la_tasa}), que es{' '}
                  {(Number(simulacion.tasa_mensual) * 100).toFixed(2)} % mensual.
                </p>
                <div className="mt-2 flex flex-wrap items-end gap-3">
                  <label className="text-xs text-slate-600">
                    Pagando al mes
                    <input
                      type="number"
                      value={pago}
                      placeholder={String(Math.round(Number(simulacion.pago_mensual)))}
                      onChange={(e) => setPago(e.target.value)}
                      className="ml-2 w-32 rounded border border-slate-300 px-2 py-1 text-sm"
                    />
                  </label>
                  <button
                    onClick={() => simular(pago)}
                    className="rounded-lg bg-slate-800 px-3 py-2 text-xs font-medium text-white"
                  >
                    Simular
                  </button>
                  {Number(simulacion.pago_mensual) !== Number(simulacion.cuota_actual) && (
                    <button
                      onClick={() => {
                        setPago('')
                        void simular('')
                      }}
                      className="text-xs text-slate-500 underline"
                    >
                      volver a la cuota actual
                    </button>
                  )}
                </div>
                <dl className="mt-3 grid grid-cols-2 gap-3 text-sm">
                  <div>
                    <dt className="text-xs uppercase text-slate-500">Saldo</dt>
                    <dd className="font-semibold">{fmtMoney(simulacion.saldo)}</dd>
                  </div>
                  <div>
                    <dt className="text-xs uppercase text-slate-500">Pagando</dt>
                    <dd className="font-semibold">{fmtMoney(simulacion.pago_mensual)}</dd>
                  </div>
                  <div>
                    <dt className="text-xs uppercase text-slate-500">Terminas en</dt>
                    <dd className="font-semibold">
                      {simulacion.viable ? `${simulacion.meses} meses` : 'nunca (el pago no cubre los intereses)'}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-xs uppercase text-slate-500">Intereses totales</dt>
                    <dd className="font-semibold text-rose-600">
                      {fmtMoney(simulacion.total_intereses)}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-xs uppercase text-slate-500">Total a pagar</dt>
                    <dd className="font-semibold">{fmtMoney(simulacion.total_pagado)}</dd>
                  </div>
                  {simulacion.cuota_actual && (
                    <div>
                      <dt className="text-xs uppercase text-slate-500">Tu cuota de este mes</dt>
                      <dd className="font-semibold">{fmtMoney(simulacion.cuota_actual)}</dd>
                    </div>
                  )}
                </dl>
              </>
            )
          )}
        </section>
      </div>

      <section className="rounded-xl border border-slate-200 bg-white p-4">
        <h2 className="text-lg font-semibold text-slate-700">Auditoría extracto ↔ Konta</h2>
        <p className="text-xs text-slate-500">
          Que lo que dice el banco cuadre con lo que tienes registrado. Es lo que descubre un
          movimiento sin importar o uno repetido.
        </p>
        <ul className="mt-3 space-y-2">
          {extractos.map((x) => (
            <li key={x.id} className="rounded-lg border border-slate-200 p-3">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-sm font-medium text-slate-800">
                  {x.banco ?? 'Extracto'} · {x.nombre_archivo}
                </span>
                <button
                  onClick={() => auditar(x.id)}
                  className="ml-auto text-xs text-slate-600 underline"
                >
                  {auditorias[x.id] ? 'volver a revisar' : 'revisar'}
                </button>
              </div>
              {auditorias[x.id] && (
                <ul className="mt-2 space-y-1 text-xs">
                  {auditorias[x.id].map((hallazgo) => (
                    <li key={hallazgo.nombre}>
                      <span
                        className={
                          hallazgo.ok === true
                            ? 'text-emerald-700'
                            : hallazgo.ok === false
                              ? 'text-rose-700'
                              : 'text-slate-500'
                        }
                      >
                        {hallazgo.ok === true ? '✅' : hallazgo.ok === false ? '❌' : '➖'}{' '}
                        {hallazgo.nombre}
                      </span>
                      <span className="text-slate-500"> · {hallazgo.detalle}</span>
                      {hallazgo.sugerencia && (
                        <div className="pl-5 text-amber-700">{hallazgo.sugerencia}</div>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </li>
          ))}
          {extractos.length === 0 && (
            <li className="text-sm text-slate-500">Todavía no hay extractos.</li>
          )}
        </ul>
      </section>
    </div>
  )
}
