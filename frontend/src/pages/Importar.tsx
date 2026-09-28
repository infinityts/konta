import { useState, type ChangeEvent } from 'react'
import { api, apiUpload } from '../api'
import { fmtMoney, type ImportarFila } from '../types'

export default function Importar() {
  const [filas, setFilas] = useState<ImportarFila[]>([])
  const [tipoDefault, setTipoDefault] = useState('gasto')
  const [mensaje, setMensaje] = useState('')
  const [error, setError] = useState('')
  const [cargando, setCargando] = useState(false)

  async function subir(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    setCargando(true)
    setError('')
    setMensaje('')
    setFilas([])
    try {
      const fd = new FormData()
      fd.append('archivo', file)
      const r = await apiUpload<{ filas: ImportarFila[]; total: number }>(
        `/importar/csv?tipo_default=${tipoDefault}`,
        fd,
      )
      setFilas(r.filas)
      setMensaje(`${r.total} fila(s) detectada(s). Revisa y confirma la importación.`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al leer el CSV')
    } finally {
      setCargando(false)
      e.target.value = ''
    }
  }

  async function confirmar() {
    setCargando(true)
    setError('')
    try {
      const r = await api<{ creadas: number }>('/importar/confirmar', {
        method: 'POST',
        body: JSON.stringify({ filas }),
      })
      setMensaje(`✅ ${r.creadas} transacción(es) importada(s).`)
      setFilas([])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al importar')
    } finally {
      setCargando(false)
    }
  }

  return (
    <div>
      <h2 className="text-xl font-semibold">Importar estado de cuenta (CSV)</h2>
      {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
      {mensaje && <p className="mt-2 text-sm text-emerald-700">{mensaje}</p>}

      <div className="mt-4 rounded-xl border border-slate-200 bg-white p-5">
        <p className="text-sm text-slate-600">
          Sube el CSV de tu banco. Se detectan solas las columnas de fecha, descripción y monto.
          Si el CSV no trae signos, se usa el tipo por defecto.
        </p>
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <select
            value={tipoDefault}
            onChange={(e) => setTipoDefault(e.target.value)}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
          >
            <option value="gasto">Tipo por defecto: Gasto</option>
            <option value="ingreso">Tipo por defecto: Ingreso</option>
          </select>
          <input
            type="file"
            accept=".csv,text/csv"
            onChange={subir}
            disabled={cargando}
            className="block text-sm text-slate-600 file:mr-4 file:rounded-lg file:border-0 file:bg-indigo-600 file:px-4 file:py-2 file:text-sm file:font-medium file:text-white hover:file:bg-indigo-700"
          />
        </div>
        {cargando && <p className="mt-2 text-sm text-slate-500">Procesando…</p>}
      </div>

      {filas.length > 0 && (
        <div className="mt-4 rounded-xl border border-slate-200 bg-white p-5">
          <div className="flex items-center justify-between">
            <h3 className="font-medium text-slate-700">Previsualización ({filas.length})</h3>
            <button
              onClick={confirmar}
              disabled={cargando}
              className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700"
            >
              Confirmar importación
            </button>
          </div>
          <div className="mt-3 overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-200 text-left text-slate-500">
                  <th className="py-2 pr-4">Fecha</th>
                  <th className="py-2 pr-4">Descripción</th>
                  <th className="py-2 pr-4">Tipo</th>
                  <th className="py-2 text-right">Monto</th>
                </tr>
              </thead>
              <tbody>
                {filas.map((f, i) => (
                  <tr key={i} className="border-b border-slate-100">
                    <td className="py-1.5 pr-4">{f.fecha}</td>
                    <td className="py-1.5 pr-4 text-slate-600">{f.descripcion ?? '—'}</td>
                    <td className="py-1.5 pr-4">
                      <span className={f.tipo === 'gasto' ? 'text-red-600' : 'text-emerald-600'}>{f.tipo}</span>
                    </td>
                    <td className="py-1.5 text-right font-medium">{fmtMoney(f.monto)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
