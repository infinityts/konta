import { useEffect, useState } from 'react'
import { api } from '../api'
import type { CuotaIa, OrdenPago, Pago, PaqueteLecturas, PlanIa } from '../types'

const pesos = (v: string | number) => `$${Number(v).toLocaleString('es-CO')}`

/** El almacenamiento de un plan, en palabras. */
function almacenamiento(pl: PlanIa): string {
  const peso =
    pl.almacenamiento_mb != null && pl.almacenamiento_mb >= 1024
      ? `${(pl.almacenamiento_mb / 1024).toFixed(pl.almacenamiento_mb % 1024 === 0 ? 0 : 1)} GB`
      : `${pl.almacenamiento_mb ?? 0} MB`
  const archivos =
    pl.archivos_incluidos == null ? 'archivos ilimitados' : `${pl.archivos_incluidos} archivos`
  return `${archivos} · ${pl.retencion_dias ?? 7} días · ${peso}`
}

/**
 * Planes, paquetes de lecturas y recibos.
 *
 * El precio y lo que incluye cada plan los pone el servidor (el catálogo es datos, no código): aquí
 * solo se elige. Con la pasarela simulada —la que hay hoy en desarrollo— el botón de pagar lo dice
 * claro, porque **no se cobra nada**: es para poder recorrer el circuito completo antes de conectar
 * la pasarela real.
 */
export default function Planes() {
  const [planes, setPlanes] = useState<PlanIa[]>([])
  const [paquetes, setPaquetes] = useState<PaqueteLecturas[]>([])
  const [cuota, setCuota] = useState<CuotaIa | null>(null)
  const [recibos, setRecibos] = useState<Pago[]>([])
  const [orden, setOrden] = useState<OrdenPago | null>(null)
  const [aviso, setAviso] = useState('')
  const [error, setError] = useState('')
  const [ocupado, setOcupado] = useState('')

  async function cargar() {
    try {
      const [p, q, c, r] = await Promise.all([
        api<PlanIa[]>('/ia/planes'),
        api<PaqueteLecturas[]>('/pagos/paquetes'),
        api<CuotaIa>('/ia/cuota'),
        api<Pago[]>('/pagos/mios'),
      ])
      setPlanes(p)
      setPaquetes(q)
      setCuota(c)
      setRecibos(r)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No pude traer los planes')
    }
  }
  useEffect(() => {
    void cargar()
  }, [])

  /** Crea la orden; si la pasarela devuelve una URL, se va hacia ella. */
  async function comprar(tipo: 'plan' | 'paquete', codigo: string) {
    setOcupado(codigo)
    setError('')
    setAviso('')
    try {
      const nueva = await api<OrdenPago>('/pagos/orden', {
        method: 'POST',
        body: JSON.stringify({ tipo, codigo }),
      })
      if (nueva.url) {
        window.location.href = nueva.url
        return
      }
      setOrden(nueva)
      setAviso(
        `Orden creada por ${pesos(nueva.monto)}. Falta el pago: revisa abajo y confírmalo.`,
      )
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No pude crear la orden')
    } finally {
      setOcupado('')
    }
  }

  /** Confirma el pago con la pasarela simulada (no cobra nada). */
  async function confirmarSimulado(referencia: string) {
    setOcupado(referencia)
    try {
      const r = await api<{ mensaje: string }>(`/pagos/simular-pago/${referencia}`, {
        method: 'POST',
      })
      setAviso(r.mensaje ?? 'Pago confirmado.')
      setOrden(null)
      await cargar()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No pude confirmar el pago')
    } finally {
      setOcupado('')
    }
  }

  return (
    <div className="max-w-4xl space-y-6">
      <div>
        <h2 className="text-xl font-semibold">Planes y lecturas</h2>
        {cuota && (
          <p className="mt-1 text-sm text-slate-500">
            Tu plan es <strong>{cuota.plan}</strong> · te quedan {cuota.lecturas_restantes} lecturas
            con IA y {cuota.consultas_restantes} consultas al asistente este mes · guardas{' '}
            {cuota.archivos_usados} archivos ({cuota.mb_usados} MB, se borran a los{' '}
            {cuota.retencion_dias} días).
          </p>
        )}
        {cuota?.plan_hasta && (
          <p
            className={`mt-1 text-sm ${
              cuota.plan_por_vencer ? 'font-medium text-amber-700' : 'text-slate-500'
            }`}
          >
            {cuota.plan_por_vencer ? '⏳' : '📅'} Tu plan {cuota.plan} vence el{' '}
            {cuota.plan_hasta.slice(0, 10)}
            {cuota.dias_de_plan != null && cuota.dias_de_plan >= 0
              ? ` (en ${cuota.dias_de_plan} días)`
              : ' (vencido)'}
            {cuota.plan_por_vencer &&
              ' — renuévalo aquí abajo para no volver al plan base.'}
          </p>
        )}
      </div>

      {aviso && (
        <p className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800">
          {aviso}
        </p>
      )}
      {error && (
        <p className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
          {error}
        </p>
      )}

      {orden && (
        <div className="rounded-xl border border-indigo-200 bg-indigo-50 p-4">
          <p className="text-sm text-indigo-900">
            <strong>Orden {orden.referencia}</strong> · {pesos(orden.monto)} ·{' '}
            {orden.tipo === 'plan' ? `plan ${orden.codigo}` : `paquete ${orden.codigo}`}
          </p>
          {orden.pasarela === 'simulada' ? (
            <>
              <p className="mt-1 text-xs text-indigo-700">
                La pasarela está en modo <strong>prueba</strong>: este botón acredita la compra
                <strong> sin cobrar nada</strong>. Sirve para recorrer el circuito completo.
              </p>
              <button
                onClick={() => void confirmarSimulado(orden.referencia)}
                disabled={ocupado === orden.referencia}
                className="mt-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
              >
                {ocupado === orden.referencia ? 'Confirmando…' : 'Confirmar el pago (prueba)'}
              </button>
            </>
          ) : (
            <p className="mt-1 text-xs text-indigo-700">
              {orden.instrucciones ?? 'Termina el pago en la pasarela.'}
            </p>
          )}
        </div>
      )}

      <div className="grid gap-3 sm:grid-cols-2">
        {planes.map((pl) => (
          <div
            key={pl.codigo}
            className={`rounded-xl border p-4 ${
              pl.codigo === cuota?.plan ? 'border-indigo-300 bg-indigo-50' : 'border-slate-200 bg-white'
            }`}
          >
            <div className="flex items-baseline justify-between gap-2">
              <h3 className="font-semibold text-slate-800">{pl.nombre}</h3>
              <span className="text-sm font-medium text-slate-700">{pesos(pl.precio_mes)}/mes</span>
            </div>
            {pl.codigo === cuota?.plan && (
              <p className="mt-0.5 text-xs font-medium text-indigo-700">tu plan</p>
            )}
            <ul className="mt-2 space-y-1 text-sm text-slate-600">
              <li>· {pl.lecturas_ia} lecturas con IA al mes</li>
              <li>· {pl.consultas_asistente} consultas al asistente</li>
              <li>· {almacenamiento(pl)}</li>
            </ul>
            <button
              onClick={() => void comprar('plan', pl.codigo)}
              disabled={ocupado === pl.codigo || pl.codigo === cuota?.plan}
              className="mt-3 w-full rounded-lg bg-indigo-600 px-3 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
            >
              {pl.codigo === cuota?.plan
                ? 'Ya es tu plan'
                : ocupado === pl.codigo
                  ? 'Creando la orden…'
                  : `Cambiar a ${pl.nombre}`}
            </button>
          </div>
        ))}
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-4">
        <h3 className="font-semibold text-slate-800">Lecturas sueltas</h3>
        <p className="mt-0.5 text-sm text-slate-500">
          Si te quedas sin lecturas y no quieres cambiar de plan.
        </p>
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          {paquetes.map((pa) => (
            <div key={pa.codigo} className="flex items-center justify-between gap-3 rounded-lg border border-slate-200 p-3">
              <span className="text-sm text-slate-700">
                {pa.nombre} · <strong>{pesos(pa.precio)}</strong>
              </span>
              <button
                onClick={() => void comprar('paquete', pa.codigo)}
                disabled={ocupado === pa.codigo}
                className="rounded-lg border border-indigo-300 px-3 py-1.5 text-sm text-indigo-700 hover:bg-indigo-50 disabled:opacity-50"
              >
                {ocupado === pa.codigo ? 'Creando…' : 'Comprar'}
              </button>
            </div>
          ))}
          {paquetes.length === 0 && (
            <p className="text-sm text-slate-400">No hay paquetes disponibles ahora mismo.</p>
          )}
        </div>
      </div>

      <div className="rounded-xl border border-slate-200 bg-white">
        <h3 className="border-b border-slate-100 px-4 py-2 font-semibold text-slate-800">Tus recibos</h3>
        {recibos.length === 0 ? (
          <p className="px-4 py-3 text-sm text-slate-400">Todavía no has comprado nada.</p>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-left text-xs text-slate-500">
              <tr>
                <th className="px-4 py-2">Fecha</th>
                <th className="px-4 py-2">Qué</th>
                <th className="px-4 py-2">Monto</th>
                <th className="px-4 py-2">Estado</th>
              </tr>
            </thead>
            <tbody>
              {recibos.map((r) => (
                <tr key={r.referencia} className="border-t border-slate-100">
                  <td className="px-4 py-2 text-slate-500">{r.creado_en.slice(0, 10)}</td>
                  <td className="px-4 py-2 text-slate-700">
                    {r.tipo === 'plan' ? 'Plan' : 'Paquete'} {r.codigo}
                  </td>
                  <td className="px-4 py-2">{pesos(r.monto)}</td>
                  <td className="px-4 py-2">
                    <span
                      className={
                        r.estado === 'pagado'
                          ? 'text-emerald-700'
                          : r.estado === 'pendiente'
                            ? 'text-amber-700'
                            : 'text-slate-500'
                      }
                    >
                      {r.estado}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <p className="text-xs text-slate-400">
        El cobro en línea con la pasarela real está pendiente de conectar (necesita las credenciales
        del comercio). Mientras tanto, la compra se puede probar en modo prueba sin que se cobre
        nada, y el plan o las lecturas quedan acreditados igual.
      </p>
    </div>
  )
}
