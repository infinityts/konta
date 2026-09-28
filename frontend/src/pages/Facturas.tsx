import { useEffect, useState, type ChangeEvent } from 'react'
import { api, apiUpload } from '../api'
import { fmtMoney, type Factura, type Transaccion } from '../types'

export default function Facturas() {
  const [items, setItems] = useState<Factura[]>([])
  const [transacciones, setTransacciones] = useState<Transaccion[]>([])
  const [sel, setSel] = useState<Record<string, string>>({})
  const [subiendo, setSubiendo] = useState(false)
  const [error, setError] = useState('')

  async function cargar() {
    setItems(await api<Factura[]>('/facturas'))
    setTransacciones(await api<Transaccion[]>('/transacciones'))
  }

  useEffect(() => {
    cargar().catch((e) => setError(e instanceof Error ? e.message : 'Error'))
  }, [])

  async function subir(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    setSubiendo(true)
    setError('')
    try {
      const fd = new FormData()
      fd.append('archivo', file)
      await apiUpload<Factura>('/facturas', fd)
      await cargar()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al subir la factura')
    } finally {
      setSubiendo(false)
      e.target.value = ''
    }
  }

  async function asociar(facturaId: string) {
    const txId = sel[facturaId]
    if (!txId) return
    await api(`/facturas/${facturaId}/asociar`, {
      method: 'POST',
      body: JSON.stringify({ transaccion_id: txId }),
    })
    cargar()
  }

  async function eliminar(id: string) {
    await api(`/facturas/${id}`, { method: 'DELETE' })
    cargar()
  }

  const descTx = (t: Transaccion) => `${t.fecha} · ${t.descripcion ?? t.tipo} · ${fmtMoney(t.monto)}`

  return (
    <div>
      <h2 className="text-xl font-semibold">Facturas (PDF)</h2>
      {error && <p className="mt-2 text-sm text-red-600">{error}</p>}

      <div className="mt-4 rounded-xl border border-slate-200 bg-white p-5">
        <p className="text-sm text-slate-600">
          Sube una factura en PDF. Se extrae el texto (con OCR si es escaneada) y se intentan detectar el monto y la fecha.
        </p>
        <input
          type="file"
          accept="application/pdf"
          onChange={subir}
          disabled={subiendo}
          className="mt-3 block w-full text-sm text-slate-600 file:mr-4 file:rounded-lg file:border-0 file:bg-indigo-600 file:px-4 file:py-2 file:text-sm file:font-medium file:text-white hover:file:bg-indigo-700"
        />
        {subiendo && <p className="mt-2 text-sm text-slate-500">Procesando PDF…</p>}
      </div>

      <ul className="mt-4 space-y-3">
        {items.map((f) => (
          <li key={f.id} className="rounded-xl border border-slate-200 bg-white p-4">
            <div className="flex items-start justify-between">
              <div>
                <p className="font-medium">{f.nombre_archivo}</p>
                <p className="text-sm text-slate-500">
                  Monto detectado: <span className="font-medium text-slate-700">{f.monto_detectado != null ? fmtMoney(f.monto_detectado) : '—'}</span>
                  {' · '}Fecha: {f.fecha_detectada ?? '—'}
                </p>
                {f.transaccion_id ? (
                  <p className="mt-1 text-xs text-emerald-600">✓ Asociada a una transacción</p>
                ) : (
                  <p className="mt-1 text-xs text-amber-600">Sin asociar</p>
                )}
              </div>
              <button onClick={() => eliminar(f.id)} className="text-sm text-red-600 hover:underline">Eliminar</button>
            </div>

            {!f.transaccion_id && transacciones.length > 0 && (
              <div className="mt-3 flex flex-wrap items-center gap-2">
                <select
                  value={sel[f.id] ?? ''}
                  onChange={(e) => setSel((s) => ({ ...s, [f.id]: e.target.value }))}
                  className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
                >
                  <option value="">Asociar a transacción…</option>
                  {transacciones.slice(0, 50).map((t) => (
                    <option key={t.id} value={t.id}>{descTx(t)}</option>
                  ))}
                </select>
                <button onClick={() => asociar(f.id)} className="rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-700 hover:bg-slate-50">
                  Asociar
                </button>
              </div>
            )}

            {f.texto_extraido && (
              <details className="mt-3">
                <summary className="cursor-pointer text-sm text-slate-500">Ver texto extraído</summary>
                <pre className="mt-2 max-h-40 overflow-auto whitespace-pre-wrap rounded-lg bg-slate-50 p-3 text-xs text-slate-600">
                  {f.texto_extraido.slice(0, 1500)}
                </pre>
              </details>
            )}
          </li>
        ))}
        {items.length === 0 && <p className="text-sm text-slate-500">Aún no has subido facturas.</p>}
      </ul>
    </div>
  )
}
