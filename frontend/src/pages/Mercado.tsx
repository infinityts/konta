import { useEffect, useState } from 'react'
import { api } from '../api'
import { fmtMoney, type Comparativo, type ItemLista, type ListaMercado, type Producto } from '../types'

export default function Mercado() {
  const [lista, setLista] = useState<ListaMercado>({ items: [], total_estimado: 0, pendientes: 0 })
  const [productos, setProductos] = useState<Producto[]>([])
  const [itemForm, setItemForm] = useState({ nombre: '', cantidad: '1', precio_estimado: '' })
  const [prodForm, setProdForm] = useState({ nombre: '', unidad: '' })
  const [precioForm, setPrecioForm] = useState({ tienda: '', precio: '' })
  const [selProducto, setSelProducto] = useState('')
  const [comparativo, setComparativo] = useState<Comparativo | null>(null)
  const [error, setError] = useState('')

  async function cargar() {
    setLista(await api<ListaMercado>('/lista-mercado'))
    setProductos(await api<Producto[]>('/productos'))
  }

  useEffect(() => {
    cargar().catch((e) => setError(e instanceof Error ? e.message : 'Error'))
  }, [])

  async function verComparativo(pid: string) {
    setSelProducto(pid)
    setComparativo(null)
    if (!pid) return
    setComparativo(await api<Comparativo>(`/productos/${pid}/comparativo`))
  }

  async function agregarItem() {
    if (!itemForm.nombre) return
    await api('/lista-mercado', {
      method: 'POST',
      body: JSON.stringify({
        nombre: itemForm.nombre,
        cantidad: itemForm.cantidad || '1',
        precio_estimado: itemForm.precio_estimado || null,
      }),
    })
    setItemForm({ nombre: '', cantidad: '1', precio_estimado: '' })
    cargar()
  }

  async function toggleItem(item: ItemLista) {
    await api(`/lista-mercado/${item.id}`, { method: 'PATCH', body: JSON.stringify({ comprado: !item.comprado }) })
    cargar()
  }

  async function eliminarItem(id: string) {
    await api(`/lista-mercado/${id}`, { method: 'DELETE' })
    cargar()
  }

  async function crearProducto() {
    if (!prodForm.nombre) return
    await api('/productos', { method: 'POST', body: JSON.stringify({ nombre: prodForm.nombre, unidad: prodForm.unidad || null }) })
    setProdForm({ nombre: '', unidad: '' })
    cargar()
  }

  async function registrarPrecio() {
    if (!selProducto || !precioForm.precio) return
    await api(`/productos/${selProducto}/precios`, {
      method: 'POST',
      body: JSON.stringify({ tienda: precioForm.tienda || null, precio: precioForm.precio }),
    })
    setPrecioForm({ tienda: '', precio: '' })
    await verComparativo(selProducto)
  }

  return (
    <div>
      <h2 className="text-xl font-semibold">Mercado</h2>
      {error && <p className="mt-2 text-sm text-red-600">{error}</p>}

      {/* Lista de mercado */}
      <div className="mt-4 rounded-xl border border-slate-200 bg-white p-5">
        <div className="flex items-center justify-between">
          <h3 className="font-medium text-slate-700">Lista de mercado</h3>
          <span className="text-sm text-slate-500">{lista.pendientes} pendiente(s) · {fmtMoney(lista.total_estimado)}</span>
        </div>

        <div className="mt-3 flex flex-wrap gap-2">
          <input placeholder="Producto" value={itemForm.nombre} onChange={(e) => setItemForm((f) => ({ ...f, nombre: e.target.value }))} className="flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm" />
          <input placeholder="Cant." value={itemForm.cantidad} onChange={(e) => setItemForm((f) => ({ ...f, cantidad: e.target.value }))} className="w-20 rounded-lg border border-slate-300 px-3 py-2 text-sm" />
          <input placeholder="Precio est." value={itemForm.precio_estimado} onChange={(e) => setItemForm((f) => ({ ...f, precio_estimado: e.target.value }))} className="w-32 rounded-lg border border-slate-300 px-3 py-2 text-sm" />
          <button onClick={agregarItem} className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700">Agregar</button>
        </div>

        <ul className="mt-4 divide-y divide-slate-100">
          {lista.items.map((it) => (
            <li key={it.id} className="flex items-center justify-between py-2">
              <label className="flex items-center gap-3 text-sm">
                <input type="checkbox" checked={it.comprado} onChange={() => toggleItem(it)} className="h-4 w-4" />
                <span className={it.comprado ? 'text-slate-400 line-through' : 'text-slate-800'}>
                  {it.nombre} {Number(it.cantidad) !== 1 ? `× ${it.cantidad}` : ''}
                </span>
              </label>
              <div className="flex items-center gap-3 text-sm">
                <span className="text-slate-600">{it.precio_estimado != null ? fmtMoney(it.precio_estimado) : '—'}</span>
                <button onClick={() => eliminarItem(it.id)} className="text-red-600 hover:underline">Eliminar</button>
              </div>
            </li>
          ))}
          {lista.items.length === 0 && <li className="py-2 text-sm text-slate-500">La lista está vacía.</li>}
        </ul>
      </div>

      {/* Comparativo de precios */}
      <div className="mt-6 rounded-xl border border-slate-200 bg-white p-5">
        <h3 className="font-medium text-slate-700">Comparativo de precios</h3>

        <div className="mt-3 flex flex-wrap items-center gap-2">
          <select value={selProducto} onChange={(e) => verComparativo(e.target.value)} className="rounded-lg border border-slate-300 px-3 py-2 text-sm">
            <option value="">Elige un producto…</option>
            {productos.map((p) => (
              <option key={p.id} value={p.id}>{p.nombre}</option>
            ))}
          </select>
          <input placeholder="Nuevo producto" value={prodForm.nombre} onChange={(e) => setProdForm((f) => ({ ...f, nombre: e.target.value }))} className="rounded-lg border border-slate-300 px-3 py-2 text-sm" />
          <input placeholder="Unidad (opcional)" value={prodForm.unidad} onChange={(e) => setProdForm((f) => ({ ...f, unidad: e.target.value }))} className="w-36 rounded-lg border border-slate-300 px-3 py-2 text-sm" />
          <button onClick={crearProducto} className="rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-700 hover:bg-slate-50">Crear producto</button>
        </div>

        {selProducto && (
          <>
            <div className="mt-4 flex flex-wrap items-center gap-2">
              <input placeholder="Tienda" value={precioForm.tienda} onChange={(e) => setPrecioForm((f) => ({ ...f, tienda: e.target.value }))} className="rounded-lg border border-slate-300 px-3 py-2 text-sm" />
              <input placeholder="Precio" value={precioForm.precio} onChange={(e) => setPrecioForm((f) => ({ ...f, precio: e.target.value }))} className="w-32 rounded-lg border border-slate-300 px-3 py-2 text-sm" />
              <button onClick={registrarPrecio} className="rounded-lg bg-indigo-600 px-3 py-2 text-sm text-white hover:bg-indigo-700">Registrar precio</button>
            </div>

            {comparativo && (
              <div className="mt-4">
                {comparativo.tiendas.length === 0 ? (
                  <p className="text-sm text-slate-500">Aún no hay precios para este producto.</p>
                ) : (
                  <>
                    {comparativo.mas_barata && (
                      <p className="text-sm text-emerald-700">💡 Más barato en <strong>{comparativo.mas_barata}</strong></p>
                    )}
                    <ul className="mt-2 divide-y divide-slate-100">
                      {comparativo.tiendas.map((t, i) => (
                        <li key={t.tienda} className="flex items-center justify-between py-2 text-sm">
                          <span className={i === 0 ? 'font-medium text-emerald-700' : 'text-slate-700'}>{t.tienda}</span>
                          <span className="text-slate-600">{fmtMoney(t.precio)} · {t.fecha}</span>
                        </li>
                      ))}
                    </ul>
                  </>
                )}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}
