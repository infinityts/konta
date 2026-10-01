import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { mesLocal } from '../utils/fechas'
import { api } from '../api'
import {
  fmtMoney,
  type Alerta,
  type Categoria,
  type Diagnostico,
  type Etiqueta,
  type Suscripcion,
  type Transaccion,
} from '../types'

const ETIQUETA_ALERTA: Record<string, string> = {
  suscripcion: 'suscripción',
  tarjeta_pago: 'pago tarjeta',
  tarjeta_corte: 'corte tarjeta',
}

/** "2026-09-30" -> "30 sep" */
function fmtFecha(iso: string): string {
  const d = new Date(`${iso}T00:00:00`)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleDateString('es-CO', { day: 'numeric', month: 'short' }).replace('.', '')
}

/** 2 -> "en 2 días" · 1 -> "mañana" · 0 -> "hoy" · -3 -> "vencido hace 3 días" */
function fmtDias(n: number): string {
  if (n < 0) return `vencido hace ${Math.abs(n)} día${Math.abs(n) === 1 ? '' : 's'}`
  if (n === 0) return 'hoy'
  if (n === 1) return 'mañana'
  return `en ${n} días`
}

function Kpi({
  label,
  value,
  detalle,
  tono = 'slate',
}: {
  label: string
  value: string
  detalle?: string
  tono?: 'slate' | 'rojo'
}) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <p className="text-[13px] text-slate-500">{label}</p>
      <p
        className={`mt-1.5 text-2xl font-semibold tabular-nums ${
          tono === 'rojo' ? 'text-red-600' : 'text-slate-900'
        }`}
      >
        {value}
      </p>
      {detalle && <p className="mt-1 text-xs text-slate-400">{detalle}</p>}
    </div>
  )
}

/** Tarjeta de una fila con icono, texto secundario y valor a la derecha. */
function Fila({
  icono,
  claseIcono,
  titulo,
  detalle,
  valor,
  subvalor,
  colorValor,
}: {
  icono: string
  claseIcono: string
  titulo: string
  detalle?: string
  valor?: string
  subvalor?: string
  colorValor?: string
}) {
  return (
    <div className="flex items-start gap-3 border-b border-slate-100 py-3 text-sm last:border-b-0">
      <span className={`flex h-7 w-7 flex-none items-center justify-center rounded-lg text-[13px] ${claseIcono}`}>
        {icono}
      </span>
      <div className="min-w-0">
        <p className="text-slate-700">{titulo}</p>
        {detalle && <p className="mt-0.5 text-xs text-slate-400">{detalle}</p>}
      </div>
      {valor && (
        <div className="ml-auto flex-none text-right">
          <p className={`font-semibold tabular-nums ${colorValor ?? 'text-slate-900'}`}>{valor}</p>
          {subvalor && <p className="text-xs text-slate-400">{subvalor}</p>}
        </div>
      )}
    </div>
  )
}

export default function Dashboard() {
  const [transacciones, setTransacciones] = useState<Transaccion[]>([])
  const [suscripciones, setSuscripciones] = useState<Suscripcion[]>([])
  const [categorias, setCategorias] = useState<Categoria[]>([])
  const [etiquetas, setEtiquetas] = useState<Etiqueta[]>([])
  const [alertas, setAlertas] = useState<Alerta[]>([])
  const [diag, setDiag] = useState<Diagnostico | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    Promise.all([
      api<Transaccion[]>('/transacciones'),
      api<Suscripcion[]>('/suscripciones'),
      api<Categoria[]>('/categorias'),
      api<Etiqueta[]>('/etiquetas'),
      api<Alerta[]>('/alertas?dias=15'),
      api<Diagnostico>('/saldos/diagnostico'),
    ])
      .then(([t, s, c, e, al, d]) => {
        setTransacciones(t)
        setSuscripciones(s)
        setCategorias(c)
        setEtiquetas(e)
        setAlertas(al)
        setDiag(d)
      })
      .catch((e) => setError(e instanceof Error ? e.message : 'Error'))
  }, [])

  const now = new Date()
  const mes = mesLocal()
  const mesLabel = now.toLocaleDateString('es-CO', { month: 'long', year: 'numeric' })

  const delMes = transacciones.filter((t) => t.fecha.startsWith(mes))
  const ingresoMes = delMes.filter((t) => t.tipo === 'ingreso').reduce((a, t) => a + Number(t.monto), 0)
  const gastoMes = delMes.filter((t) => t.tipo === 'gasto').reduce((a, t) => a + Number(t.monto), 0)

  const activas = suscripciones.filter((s) => s.estado === 'activa')

  // "Categoría › Etiqueta › Subetiqueta"
  const etiquetaCompleta = (catId: string | null, etqId: string | null): string => {
    const partes = [categorias.find((c) => c.id === catId)?.nombre ?? 'Sin categoría']
    const e = etiquetas.find((x) => x.id === etqId)
    if (e) {
      const padre = e.padre_id ? etiquetas.find((x) => x.id === e.padre_id) : null
      partes.push(padre ? `${padre.nombre} › ${e.nombre}` : e.nombre)
    }
    return partes.join(' › ')
  }

  const porCategoria = new Map<string, number>()
  for (const t of delMes) {
    if (t.tipo !== 'gasto') continue
    const key = etiquetaCompleta(t.categoria_id, t.etiqueta_id)
    porCategoria.set(key, (porCategoria.get(key) ?? 0) + Number(t.monto))
  }
  const topCategorias = [...porCategoria.entries()]
    .map(([nombre, total]) => ({ nombre, total }))
    .sort((a, b) => b.total - a.total)
    .slice(0, 6)
  const maxTop = topCategorias[0]?.total ?? 0

  const balance = ingresoMes - gastoMes

  return (
    <div>
      <h2 className="text-xl font-semibold">Resumen</h2>
      {error && <p className="mt-2 text-sm text-red-600">{error}</p>}

      {/* Falta el saldo inicial: sin esto el número no es "tu dinero" */}
      {diag && !diag.tiene_cuentas && (
        <div className="mt-4 rounded-xl border-2 border-indigo-300 bg-indigo-50 p-5">
          <p className="font-semibold text-indigo-900">👉 Falta configurar tu saldo inicial</p>
          <p className="mt-1 text-sm text-indigo-800">
            El saldo de abajo es solo el <strong>flujo</strong> de tus movimientos (ingresos − gastos),{' '}
            <strong>no tu dinero</strong>. La app no sabe cuánto tienes hasta que crees una cuenta con el
            saldo que tienes hoy.
          </p>
          <Link
            to="/cuentas"
            className="mt-3 inline-block rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700"
          >
            Crear mi cuenta con el saldo inicial
          </Link>
        </div>
      )}

      {/* 1) KPIs útiles arriba (antes: «Tarjetas: 2» y «Movimientos del mes: 1») */}
      {diag && (
        <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Kpi
            label={diag.tiene_cuentas ? 'Saldo actual' : 'Flujo acumulado'}
            value={fmtMoney(diag.saldo_actual)}
            detalle={diag.sobregirado ? 'Sobregirado' : `${activas.length} suscripciones activas`}
            tono={diag.sobregirado ? 'rojo' : 'slate'}
          />
          <Kpi
            label="Ingresos del mes"
            value={fmtMoney(ingresoMes)}
            detalle={
              diag.proximo_ingreso
                ? `+${fmtMoney(diag.proximo_ingreso.monto)} el ${fmtFecha(diag.proximo_ingreso.fecha)}`
                : 'Sin ingresos pendientes'
            }
          />
          <Kpi
            label="Gastos del mes"
            value={fmtMoney(gastoMes)}
            detalle={`${delMes.length} movimiento${delMes.length === 1 ? '' : 's'}`}
            tono={gastoMes > 0 ? 'rojo' : 'slate'}
          />
          <Kpi
            label="Gasto fijo / mes"
            value={fmtMoney(diag.gastos_fijos)}
            detalle={`${activas.length} suscripciones · anuales prorrateadas`}
          />
        </div>
      )}

      <div className="mt-4 grid gap-4 lg:grid-cols-[1.55fr_1fr]">
        {/* ---------- Columna izquierda ---------- */}
        <div className="space-y-4">
          {/* 2) Balance del mes: antes era un bloque amarillo gigante */}
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <div className="flex items-baseline justify-between">
              <h3 className="font-medium text-slate-700">Balance de {mesLabel}</h3>
              <span
                className={`text-sm font-semibold tabular-nums ${
                  balance >= 0 ? 'text-emerald-700' : 'text-amber-700'
                }`}
              >
                {balance >= 0 ? '+' : '−'}
                {fmtMoney(Math.abs(balance))}
              </span>
            </div>
            <div className="mt-3 flex gap-6 text-sm">
              <span className="text-slate-500">
                Ingresos <strong className="ml-1 font-semibold text-emerald-700">{fmtMoney(ingresoMes)}</strong>
              </span>
              <span className="text-slate-500">
                Gastos <strong className="ml-1 font-semibold text-red-700">{fmtMoney(gastoMes)}</strong>
              </span>
            </div>
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-5">
            <div className="flex items-center justify-between">
              <h3 className="font-medium text-slate-700">Top categorías del mes</h3>
              <span className="text-xs text-slate-400">gastos</span>
            </div>
            {topCategorias.length === 0 ? (
              <p className="mt-2 text-sm text-slate-500">Aún no hay gastos este mes.</p>
            ) : (
              <>
                <ul className="mt-4 space-y-3">
                  {topCategorias.map((c) => (
                    <li key={c.nombre}>
                      <div className="flex justify-between text-sm">
                        <span className="truncate pr-3 text-slate-700">{c.nombre}</span>
                        <span className="flex-none font-medium tabular-nums text-slate-900">
                          {fmtMoney(c.total)}
                        </span>
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
                {topCategorias.length < 3 && (
                  <p className="mt-4 border-t border-slate-100 pt-3 text-xs text-slate-400">
                    Con menos de 3 categorías el ranking no dice mucho todavía.
                  </p>
                )}
              </>
            )}
          </div>
        </div>

        {/* ---------- Columna derecha ---------- */}
        <div className="space-y-4">
          {/* 3) Antes: 5 bullets de prosa. Ahora: motivos con su número. */}
          {diag && diag.motivos.length > 0 && (
            <div className="rounded-xl border border-slate-200 bg-white p-5">
              <div className="flex items-center justify-between">
                <h3 className="font-medium text-slate-700">Alertas</h3>
                <span className="text-xs text-slate-400">{diag.motivos.length}</span>
              </div>
              <ul className="mt-3 space-y-2 text-sm">
                {diag.motivos.map((m, i) => (
                  <li key={i} className="flex gap-2 text-slate-600">
                    <span className={diag.sobregirado ? 'text-red-500' : 'text-amber-500'}>•</span>
                    <span>{m}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* 4) Próximos pagos con fecha corta y «en N días» */}
          <div className="rounded-xl border border-slate-200 bg-white p-5">
            <div className="flex items-center justify-between">
              <h3 className="font-medium text-slate-700">Próximos pagos</h3>
              <span className="text-xs text-slate-400">15 días</span>
            </div>
            {alertas.length === 0 ? (
              <p className="mt-2 text-sm text-slate-500">Sin pagos próximos.</p>
            ) : (
              <div className="mt-2">
                {alertas.map((a, i) => (
                  <Fila
                    key={i}
                    icono={a.tipo === 'tarjeta_corte' ? '✂️' : '💳'}
                    claseIcono="bg-amber-100"
                    titulo={a.titulo}
                    detalle={ETIQUETA_ALERTA[a.tipo] ?? a.tipo}
                    valor={fmtFecha(a.fecha)}
                    subvalor={fmtDias(a.dias_restantes)}
                    colorValor={a.dias_restantes <= 3 ? 'text-amber-600' : 'text-slate-900'}
                  />
                ))}
              </div>
            )}
          </div>

          {/* 5) Compromisos fijos: el dato de gasto_fijo del backend, no una suma propia */}
          {diag && (
            <div className="rounded-xl border border-slate-200 bg-white p-5">
              <div className="flex items-center justify-between">
                <h3 className="font-medium text-slate-700">Compromisos</h3>
                <span className="text-xs text-slate-400">al mes</span>
              </div>
              <div className="mt-2">
                <Fila
                  icono="🤖"
                  claseIcono="bg-indigo-100"
                  titulo="Suscripciones"
                  detalle="anuales ÷12 · USD a TRM oficial"
                  valor={fmtMoney(diag.gastos_fijos)}
                  subvalor={`${activas.length} activas`}
                />
                {diag.proximo_ingreso && (
                  <Fila
                    icono="💰"
                    claseIcono="bg-emerald-100"
                    titulo={diag.proximo_ingreso.nombre}
                    detalle="próximo ingreso"
                    valor={fmtMoney(diag.proximo_ingreso.monto)}
                    subvalor={fmtFecha(diag.proximo_ingreso.fecha)}
                    colorValor="text-emerald-700"
                  />
                )}
              </div>
            </div>
          )}
        </div>
      </div>

      <p className="mt-4 text-xs text-slate-400">
        <Link to="/suscripciones" className="underline">
          Revisar mis {activas.length} suscripciones
        </Link>{' '}
        · el gasto fijo convierte las anuales a mes y las de USD con la TRM oficial.
      </p>
    </div>
  )
}
