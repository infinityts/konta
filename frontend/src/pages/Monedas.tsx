import { useEffect, useState } from 'react'
import { api } from '../api'
import type { Conversion, Moneda, Tasa } from '../types'

export default function Monedas() {
  const [monedas, setMonedas] = useState<Moneda[]>([])
  const [tasas, setTasas] = useState<Tasa[]>([])
  const [tasaForm, setTasaForm] = useState({ moneda_origen: 'USD', moneda_destino: 'COP', tasa: '' })
  const [conv, setConv] = useState({ de: 'USD', a: 'COP', monto: '' })
  const [resultado, setResultado] = useState('')
  const [mensaje, setMensaje] = useState('')
  const [error, setError] = useState('')

  async function cargar() {
    setMonedas(await api<Moneda[]>('/monedas'))
    setTasas(await api<Tasa[]>('/tasas'))
  }

  useEffect(() => {
    cargar().catch((e) => setError(e instanceof Error ? e.message : 'Error'))
  }, [])

  async function crearTasa() {
    setError('')
    try {
      await api('/tasas', { method: 'POST', body: JSON.stringify(tasaForm) })
      setTasaForm((f) => ({ ...f, tasa: '' }))
      cargar()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Error al guardar la tasa')
    }
  }

  async function eliminarTasa(id: string) {
    await api(`/tasas/${id}`, { method: 'DELETE' })
    cargar()
  }

  async function actualizarInternet() {
    setError('')
    setMensaje('')
    try {
      const r = await api<{ actualizadas: number }>('/tasas/actualizar?base=USD', { method: 'POST' })
      setMensaje(`✅ ${r.actualizadas} tasas actualizadas desde internet.`)
      cargar()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo actualizar desde internet')
    }
  }

  async function convertir() {
    setError('')
    setResultado('')
    try {
      const r = await api<Conversion>(`/convertir?de=${conv.de}&a=${conv.a}&monto=${conv.monto}`)
      setResultado(`${Number(r.resultado).toLocaleString('es-CO')} ${r.a}  (tasa ${r.tasa})`)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo convertir')
    }
  }

  return (
    <div>
      <h2 className="text-xl font-semibold">Monedas y tasas de cambio</h2>
      {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
      {mensaje && <p className="mt-2 text-sm text-emerald-700">{mensaje}</p>}

      {/* Conversor */}
      <div className="mt-4 rounded-xl border border-slate-200 bg-white p-5">
        <h3 className="font-medium text-slate-700">Conversor</h3>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <input placeholder="Monto" value={conv.monto} onChange={(e) => setConv((c) => ({ ...c, monto: e.target.value }))} className="w-32 rounded-lg border border-slate-300 px-3 py-2 text-sm" />
          <select value={conv.de} onChange={(e) => setConv((c) => ({ ...c, de: e.target.value }))} className="rounded-lg border border-slate-300 px-3 py-2 text-sm">
            {monedas.map((m) => <option key={m.codigo} value={m.codigo}>{m.codigo}</option>)}
          </select>
          <span className="text-slate-400">→</span>
          <select value={conv.a} onChange={(e) => setConv((c) => ({ ...c, a: e.target.value }))} className="rounded-lg border border-slate-300 px-3 py-2 text-sm">
            {monedas.map((m) => <option key={m.codigo} value={m.codigo}>{m.codigo}</option>)}
          </select>
          <button onClick={convertir} className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700">Convertir</button>
        </div>
        {resultado && <p className="mt-3 text-lg font-semibold text-emerald-700">{resultado}</p>}
      </div>

      {/* Tasas */}
      <div className="mt-6 rounded-xl border border-slate-200 bg-white p-5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="font-medium text-slate-700">Tasas de cambio</h3>
          <button onClick={actualizarInternet} className="rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-700 hover:bg-slate-50">
            ⬇️ Actualizar desde internet
          </button>
        </div>

        <div className="mt-3 flex flex-wrap items-center gap-2">
          <select value={tasaForm.moneda_origen} onChange={(e) => setTasaForm((f) => ({ ...f, moneda_origen: e.target.value }))} className="rounded-lg border border-slate-300 px-3 py-2 text-sm">
            {monedas.map((m) => <option key={m.codigo} value={m.codigo}>{m.codigo}</option>)}
          </select>
          <span className="text-slate-400">→</span>
          <select value={tasaForm.moneda_destino} onChange={(e) => setTasaForm((f) => ({ ...f, moneda_destino: e.target.value }))} className="rounded-lg border border-slate-300 px-3 py-2 text-sm">
            {monedas.map((m) => <option key={m.codigo} value={m.codigo}>{m.codigo}</option>)}
          </select>
          <input placeholder="Tasa" value={tasaForm.tasa} onChange={(e) => setTasaForm((f) => ({ ...f, tasa: e.target.value }))} className="w-32 rounded-lg border border-slate-300 px-3 py-2 text-sm" />
          <button onClick={crearTasa} className="rounded-lg bg-indigo-600 px-3 py-2 text-sm text-white hover:bg-indigo-700">Guardar tasa</button>
        </div>

        <ul className="mt-4 max-h-72 divide-y divide-slate-100 overflow-auto">
          {tasas.map((t) => (
            <li key={t.id} className="flex items-center justify-between py-2 text-sm">
              <span className="text-slate-700">
                1 {t.moneda_origen} = <strong>{Number(t.tasa).toLocaleString('es-CO')}</strong> {t.moneda_destino}
                <span className="ml-2 text-xs text-slate-400">{t.fecha}{t.fuente ? ` · ${t.fuente}` : ''}</span>
              </span>
              <button onClick={() => eliminarTasa(t.id)} className="text-red-600 hover:underline">Eliminar</button>
            </li>
          ))}
          {tasas.length === 0 && <li className="py-2 text-sm text-slate-500">Aún no hay tasas registradas.</li>}
        </ul>
      </div>

      {/* Catálogo */}
      <div className="mt-6 rounded-xl border border-slate-200 bg-white p-5">
        <h3 className="font-medium text-slate-700">Monedas disponibles</h3>
        <div className="mt-3 flex flex-wrap gap-2">
          {monedas.map((m) => (
            <span key={m.codigo} className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-sm text-slate-600">
              {m.codigo} · {m.simbolo} · {m.nombre}
            </span>
          ))}
        </div>
      </div>
    </div>
  )
}
