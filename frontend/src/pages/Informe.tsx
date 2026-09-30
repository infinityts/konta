import { useEffect, useState } from 'react'
import { api } from '../api'

/** Un plan con sus números del mes. */
interface PlanInforme {
  codigo: string
  nombre: string
  precio_mes: number
  usuarios: number
  ingreso_cop: number
  lecturas: { total: number; promedio: number; p50: number; p90: number; max: number }
  consultas: { total: number; promedio: number; p50: number; p90: number; max: number }
  costo_ia_usd: number
  mb_dia: { total: number; promedio: number; p50: number; p90: number; max: number }
  archivos_promedio: number
  tamano_medio_archivo_mb: number
  gb_mes: number
  costo_total_cop: number | null
  margen_cop: number | null
  margen_pct: number | null
}

interface Informe {
  periodo: string
  dias_del_mes: number
  cuentas_del_dueno_excluidas: number
  usuarios: number
  ingreso_cop: number
  costo_ia_usd: number
  costo_ia_cop: number | null
  mb_dia: number
  gb_mes: number
  cop_por_usd: number | null
  planes: PlanInforme[]
  notas: string[]
}

interface UsuarioInforme {
  usuario: string
  plan: string
  precio_mes: number
  lecturas: number
  consultas: number
  tokens_entrada: number
  tokens_salida: number
  mb_dia: number
  costo_total_cop: number | null
  margen_cop: number | null
  margen_pct: number | null
  aviso: string | null
}

interface PorUsuario {
  periodo: string
  umbral_ajustado: number
  usuarios: UsuarioInforme[]
  alertas: { pierden: string[]; ajustados: string[] }
  notas: string[]
}

const pesos = (v: number | null | undefined) =>
  v == null ? '—' : `$${Math.round(v).toLocaleString('es-CO')}`

const num = (v: number | null | undefined, dec = 1) =>
  v == null ? '—' : v.toLocaleString('es-CO', { maximumFractionDigits: dec })

/**
 * El panel del dueño: cuánto cuesta de verdad cada plan y quién se está pasando.
 *
 * Es información de **todos** los clientes, así que solo la ve quien esté en
 * FINANZAS_INFORME_ADMINS; a los demás se les dice con claridad.
 */
export default function Informe() {
  const [periodo, setPeriodo] = useState('')
  const [informe, setInforme] = useState<Informe | null>(null)
  const [detalle, setDetalle] = useState<PorUsuario | null>(null)
  const [error, setError] = useState('')
  const [cargando, setCargando] = useState(true)

  useEffect(() => {
    void (async () => {
      setCargando(true)
      setError('')
      try {
        const consulta = periodo ? `?periodo=${periodo}` : ''
        setInforme(await api<Informe>(`/ia/informe${consulta}`))
        setDetalle(await api<PorUsuario>(`/ia/informe/usuarios${consulta}`))
      } catch (e) {
        setError(e instanceof Error ? e.message : 'No pude traer el informe')
        setInforme(null)
        setDetalle(null)
      } finally {
        setCargando(false)
      }
    })()
  }, [periodo])

  if (cargando) return <p className="text-sm text-slate-500">Calculando el informe…</p>

  if (error) {
    return (
      <div className="max-w-2xl rounded-xl border border-amber-200 bg-amber-50 p-4">
        <h2 className="text-lg font-semibold text-amber-900">Informe de costes</h2>
        <p className="mt-1 text-sm text-amber-800">{error}</p>
        <p className="mt-2 text-xs text-amber-700">
          Es información de todos los clientes: solo la ve el dueño de la app (el correo que esté en
          FINANZAS_INFORME_ADMINS).
        </p>
      </div>
    )
  }
  if (!informe || !detalle) return null

  const margenTotal =
    informe.costo_ia_cop != null ? informe.ingreso_cop - informe.costo_ia_cop : null

  return (
    <div className="max-w-5xl space-y-5">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-xl font-semibold">Informe de costes</h2>
        <label className="text-sm text-slate-500">
          Mes{' '}
          <input
            type="month"
            value={periodo}
            onChange={(e) => setPeriodo(e.target.value)}
            className="rounded-lg border border-slate-300 px-2 py-1 text-sm"
          />
        </label>
      </div>

      <div className="grid gap-3 sm:grid-cols-4">
        {[
          { t: 'Clientes', v: num(informe.usuarios, 0), d: `${informe.periodo}` },
          { t: 'Ingreso del mes', v: pesos(informe.ingreso_cop), d: 'lo que pagan' },
          {
            t: 'Coste real de IA',
            v: pesos(informe.costo_ia_cop),
            d: `${informe.costo_ia_usd.toFixed(4)} USD`,
          },
          {
            t: 'Margen',
            v: pesos(margenTotal),
            d: informe.cop_por_usd ? `TRM ${num(informe.cop_por_usd, 2)}` : 'sin TRM cargada',
          },
        ].map((k) => (
          <div key={k.t} className="rounded-xl border border-slate-200 bg-white p-3">
            <p className="text-xs text-slate-500">{k.t}</p>
            <p className="text-lg font-semibold text-slate-800">{k.v}</p>
            <p className="text-xs text-slate-400">{k.d}</p>
          </div>
        ))}
      </div>

      {detalle.alertas.pierden.length + detalle.alertas.ajustados.length > 0 && (
        <div className="rounded-xl border border-red-200 bg-red-50 p-3">
          <p className="text-sm font-medium text-red-900">
            {detalle.alertas.pierden.length > 0 && (
              <>Pierden dinero ({detalle.alertas.pierden.length}): {detalle.alertas.pierden.join(', ')}. </>
            )}
            {detalle.alertas.ajustados.length > 0 && (
              <>
                Se comen más del {Math.round(detalle.umbral_ajustado * 100)} % del precio (
                {detalle.alertas.ajustados.length}): {detalle.alertas.ajustados.join(', ')}.
              </>
            )}
          </p>
        </div>
      )}

      <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-xs text-slate-500">
            <tr>
              <th className="px-3 py-2">Plan</th>
              <th className="px-3 py-2">Clientes</th>
              <th className="px-3 py-2">Precio</th>
              <th className="px-3 py-2">Ingreso</th>
              <th className="px-3 py-2">Coste real</th>
              <th className="px-3 py-2">Margen</th>
              <th className="px-3 py-2">Lecturas p50 / p90</th>
              <th className="px-3 py-2">Consultas p50 / p90</th>
              <th className="px-3 py-2">MB-día</th>
              <th className="px-3 py-2">Archivo medio</th>
            </tr>
          </thead>
          <tbody>
            {informe.planes.map((p) => (
              <tr key={p.codigo} className="border-t border-slate-100">
                <td className="px-3 py-2 font-medium text-slate-700">{p.nombre}</td>
                <td className="px-3 py-2">{p.usuarios}</td>
                <td className="px-3 py-2">{pesos(p.precio_mes)}</td>
                <td className="px-3 py-2">{pesos(p.ingreso_cop)}</td>
                <td className="px-3 py-2">
                  {pesos(p.costo_total_cop)}
                  {p.costo_total_cop == null && (
                    <span className="text-xs text-slate-400"> ({p.costo_ia_usd.toFixed(4)} USD)</span>
                  )}
                </td>
                <td className="px-3 py-2">
                  {pesos(p.margen_cop)}
                  {p.margen_pct != null && (
                    <span className="text-xs text-slate-400"> ({num(p.margen_pct)} %)</span>
                  )}
                </td>
                <td className="px-3 py-2">
                  {num(p.lecturas.p50)} / {num(p.lecturas.p90)}
                </td>
                <td className="px-3 py-2">
                  {num(p.consultas.p50)} / {num(p.consultas.p90)}
                </td>
                <td className="px-3 py-2">{num(p.mb_dia.total)}</td>
                <td className="px-3 py-2">
                  {num(p.tamano_medio_archivo_mb, 2)} MB
                  <span className="text-xs text-slate-400"> ({num(p.archivos_promedio)} arch.)</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
        <p className="border-b border-slate-100 px-3 py-2 text-sm font-medium text-slate-700">
          Cliente por cliente (los que peor van, primero)
        </p>
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-xs text-slate-500">
            <tr>
              <th className="px-3 py-2">Cliente</th>
              <th className="px-3 py-2">Plan</th>
              <th className="px-3 py-2">Paga</th>
              <th className="px-3 py-2">Cuesta</th>
              <th className="px-3 py-2">Margen</th>
              <th className="px-3 py-2">Lecturas</th>
              <th className="px-3 py-2">Consultas</th>
              <th className="px-3 py-2">MB-día</th>
              <th className="px-3 py-2"></th>
            </tr>
          </thead>
          <tbody>
            {detalle.usuarios.map((u) => (
              <tr
                key={u.usuario}
                className={`border-t border-slate-100 ${
                  u.aviso === 'pierde' ? 'bg-red-50' : u.aviso === 'ajustado' ? 'bg-amber-50' : ''
                }`}
              >
                <td className="px-3 py-2 text-slate-700">{u.usuario}</td>
                <td className="px-3 py-2">{u.plan}</td>
                <td className="px-3 py-2">{pesos(u.precio_mes)}</td>
                <td className="px-3 py-2">{pesos(u.costo_total_cop)}</td>
                <td className="px-3 py-2">
                  {pesos(u.margen_cop)}
                  {u.margen_pct != null && (
                    <span className="text-xs text-slate-400"> ({num(u.margen_pct)} %)</span>
                  )}
                </td>
                <td className="px-3 py-2">{u.lecturas}</td>
                <td className="px-3 py-2">{u.consultas}</td>
                <td className="px-3 py-2">{num(u.mb_dia, 2)}</td>
                <td className="px-3 py-2 text-xs">
                  {u.aviso === 'pierde' && <span className="text-red-700">pierde dinero</span>}
                  {u.aviso === 'ajustado' && <span className="text-amber-700">ajustado</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {(informe.notas.length > 0 || detalle.notas.length > 0) && (
        <ul className="space-y-1 rounded-xl border border-slate-200 bg-slate-50 p-3 text-xs text-slate-600">
          {[...informe.notas, ...detalle.notas].map((n) => (
            <li key={n}>· {n}</li>
          ))}
          {informe.cuentas_del_dueno_excluidas > 0 && (
            <li>
              · {informe.cuentas_del_dueno_excluidas} cuenta(s) del dueño quedaron fuera: no son
              clientes.
            </li>
          )}
        </ul>
      )}
    </div>
  )
}
