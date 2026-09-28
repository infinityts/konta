import { useState, type ChangeEvent } from 'react'
import { apiDownload, apiUpload } from '../api'

export default function Respaldo() {
  const [mensaje, setMensaje] = useState('')
  const [error, setError] = useState('')
  const [cargando, setCargando] = useState(false)

  async function descargar(path: string, nombre: string) {
    setError('')
    setMensaje('')
    try {
      await apiDownload(path, nombre)
      setMensaje(`✅ Descargado: ${nombre}`)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Error al descargar')
    }
  }

  async function restaurar(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    setCargando(true)
    setError('')
    setMensaje('')
    try {
      const fd = new FormData()
      fd.append('archivo', file)
      const r = await apiUpload<{ restaurado: Record<string, number> }>('/respaldar/restaurar', fd)
      const total = Object.values(r.restaurado).reduce((a, b) => a + b, 0)
      setMensaje(`✅ Respaldo restaurado (${total} registros).`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al restaurar')
    } finally {
      setCargando(false)
      e.target.value = ''
    }
  }

  return (
    <div>
      <h2 className="text-xl font-semibold">Exportar y respaldar</h2>
      {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
      {mensaje && <p className="mt-2 text-sm text-emerald-700">{mensaje}</p>}

      <div className="mt-4 rounded-xl border border-slate-200 bg-white p-5">
        <h3 className="font-medium text-slate-700">Exportar</h3>
        <p className="mt-1 text-sm text-slate-500">
          Descarga todos tus datos (categorías, tarjetas, suscripciones, transacciones, etiquetas,
          presupuestos, mercado, etc.).
        </p>
        <div className="mt-3 flex flex-wrap gap-2">
          <button onClick={() => descargar('/exportar/json', 'konta-respaldo.json')} className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700">
            ⬇️ Respaldo completo (JSON)
          </button>
          <button onClick={() => descargar('/exportar/transacciones.csv', 'konta-transacciones.csv')} className="rounded-lg border border-slate-300 px-4 py-2 text-sm text-slate-700 hover:bg-slate-50">
            ⬇️ Transacciones (CSV)
          </button>
        </div>
      </div>

      <div className="mt-6 rounded-xl border border-amber-200 bg-amber-50 p-5">
        <h3 className="font-medium text-amber-800">Restaurar respaldo</h3>
        <p className="mt-1 text-sm text-amber-700">
          ⚠️ Restaurar un respaldo JSON <strong>reemplaza</strong> todos tus datos actuales por los del archivo.
          Úsalo solo para recuperar una copia.
        </p>
        <input
          type="file"
          accept="application/json,.json"
          onChange={restaurar}
          disabled={cargando}
          className="mt-3 block text-sm text-slate-600 file:mr-4 file:rounded-lg file:border-0 file:bg-amber-600 file:px-4 file:py-2 file:text-sm file:font-medium file:text-white hover:file:bg-amber-700"
        />
        {cargando && <p className="mt-2 text-sm text-slate-500">Restaurando…</p>}
      </div>
    </div>
  )
}
