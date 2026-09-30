import { useEffect, useState } from 'react'
import { api } from '../api'
import type { Categoria, Etiqueta, PatronIgnorado, PlantillaLector, ReglaOcr } from '../types'

const empty = { patron: '', categoria_id: '', etiqueta_id: '' }

/**
 * Lo que el clasificador del OCR ha **aprendido** de tus correcciones.
 *
 * El clasificador empareja por niveles (`historial` → `diccionario` → `embeddings`)
 * y el primero es esta tabla: cada vez que corriges la etiqueta de una línea, se
 * guarda «este texto va aquí». Hasta ahora eso era de una sola dirección: la app
 * aprendía de ti y no había forma de ver qué sabía ni de deshacer un acierto
 * equivocado. Esta pantalla es eso.
 */
export default function ReglasOcr() {
  const [items, setItems] = useState<ReglaOcr[]>([])
  // Lo que el lector ha aprendido de cada emisor (dónde viene el total y la fecha)
  const [plantillas, setPlantillas] = useState<PlantillaLector[]>([])
  // Renglones que el usuario borró y ya se descartan solos (no son artículos)
  const [patrones, setPatrones] = useState<PatronIgnorado[]>([])
  const [categorias, setCategorias] = useState<Categoria[]>([])
  const [etiquetas, setEtiquetas] = useState<Etiqueta[]>([])
  const [form, setForm] = useState(empty)
  const [editando, setEditando] = useState<string | null>(null)
  const [edicion, setEdicion] = useState({ patron: '', categoria_id: '', etiqueta_id: '' })
  const [busqueda, setBusqueda] = useState('')
  const [show, setShow] = useState(false)
  const [error, setError] = useState('')
  const [aviso, setAviso] = useState('')

  async function cargar() {
    try {
      setItems(await api<ReglaOcr[]>('/reglas-ocr'))
      setPlantillas(await api<PlantillaLector[]>('/facturas/plantillas-lector'))
      setPatrones(await api<PatronIgnorado[]>('/facturas/patrones-ignorados'))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Error')
    }
  }

  useEffect(() => {
    cargar()
    api<Categoria[]>('/categorias').then(setCategorias)
    api<Etiqueta[]>('/etiquetas').then(setEtiquetas)
  }, [])

  const etqDeCategoria = (catId: string) =>
    etiquetas.filter((e) => e.categoria_id === catId).sort((a, b) => a.nombre.localeCompare(b.nombre))

  async function crear() {
    setError('')
    setAviso('')
    try {
      await api('/reglas-ocr', {
        method: 'POST',
        body: JSON.stringify({ patron: form.patron, etiqueta_id: form.etiqueta_id }),
      })
      setForm(empty)
      setShow(false)
      setAviso('Regla guardada: ese texto irá siempre a esa etiqueta.')
      cargar()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Error al guardar la regla')
    }
  }

  function abrirEditar(r: ReglaOcr) {
    setError('')
    setAviso('')
    setEditando(r.id)
    setEdicion({ patron: r.patron, categoria_id: r.categoria_id ?? '', etiqueta_id: r.etiqueta_id })
  }

  async function guardarEdicion(id: string) {
    setError('')
    try {
      await api(`/reglas-ocr/${id}`, {
        method: 'PATCH',
        body: JSON.stringify({ patron: edicion.patron, etiqueta_id: edicion.etiqueta_id }),
      })
      setEditando(null)
      setAviso('Regla corregida.')
      cargar()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Error al corregir la regla')
    }
  }

  async function eliminar(r: ReglaOcr) {
    setError('')
    setAviso('')
    try {
      await api(`/reglas-ocr/${r.id}`, { method: 'DELETE' })
      setAviso(`Regla «${r.patron}» borrada: ese artículo volverá a clasificarse solo.`)
      cargar()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Error al borrar la regla')
    }
  }

  const q = busqueda.trim().toLowerCase()
  const visibles = items.filter(
    (r) =>
      !q ||
      r.patron.toLowerCase().includes(q) ||
      (r.etiqueta_nombre ?? '').toLowerCase().includes(q) ||
      (r.categoria_nombre ?? '').toLowerCase().includes(q),
  )

  async function borrarPatron(id: string) {
    if (!window.confirm('¿Volver a tener en cuenta este renglón?')) return
    await api(`/facturas/patrones-ignorados/${id}`, { method: 'DELETE' })
    setPatrones((ps) => ps.filter((p) => p.id !== id))
    setAviso('Ese renglón vuelve a leerse como artículo.')
  }

  async function borrarPlantilla(id: string) {
    if (!window.confirm('¿Borrar lo aprendido de este emisor?')) return
    await api(`/facturas/plantillas-lector/${id}`, { method: 'DELETE' })
    setPlantillas((ps) => ps.filter((p) => p.id !== id))
    setAviso('Plantilla borrada: esa casa se vuelve a leer adivinando.')
  }

  return (
    <>
    <div>
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold">Reglas de OCR</h2>
        <button
          onClick={() => (show ? setShow(false) : (setForm(empty), setShow(true)))}
          className="rounded-lg bg-indigo-600 px-3 py-2 text-sm font-medium text-white hover:bg-indigo-700"
        >
          {show ? 'Cancelar' : 'Enseñar una regla'}
        </button>
      </div>

      <p className="mt-1 text-sm text-slate-500">
        Lo que el clasificador ha <strong>aprendido</strong> de tus correcciones: cuando cambias
        la etiqueta de una línea de un recibo, queda anotado que ese texto va ahí. Esto es lo
        <strong> primero</strong> que mira al leer una factura (antes del diccionario), así que
        una regla equivocada manda sobre todo lo demás — bórrala y el artículo volverá a
        clasificarse solo.
      </p>

      {error && <p className="mt-2 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
      {aviso && <p className="mt-2 rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-700">{aviso}</p>}

      {show && (
        <div className="mt-4 grid gap-3 rounded-xl border border-slate-200 bg-white p-4 sm:grid-cols-3">
          <input
            placeholder="Texto del artículo (ej. PECHUGA POLLO BANDEJA)"
            value={form.patron}
            onChange={(e) => setForm((f) => ({ ...f, patron: e.target.value }))}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm sm:col-span-3"
          />
          <select
            value={form.categoria_id}
            onChange={(e) => setForm((f) => ({ ...f, categoria_id: e.target.value, etiqueta_id: '' }))}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
          >
            <option value="">Categoría…</option>
            {categorias.map((c) => (
              <option key={c.id} value={c.id}>{c.nombre}</option>
            ))}
          </select>
          <select
            value={form.etiqueta_id}
            onChange={(e) => setForm((f) => ({ ...f, etiqueta_id: e.target.value }))}
            disabled={!form.categoria_id}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm disabled:bg-slate-100"
          >
            <option value="">{form.categoria_id ? 'Etiqueta…' : 'Elige primero una categoría'}</option>
            {etqDeCategoria(form.categoria_id).map((e) => (
              <option key={e.id} value={e.id}>{e.nombre}</option>
            ))}
          </select>
          <button
            onClick={crear}
            disabled={!form.patron || !form.etiqueta_id}
            className="rounded-lg bg-indigo-600 px-3 py-2 text-sm text-white hover:bg-indigo-700 disabled:bg-slate-300"
          >
            Guardar regla
          </button>
          <p className="text-xs text-slate-500 sm:col-span-3">
            No hace falta escribir el texto exacto: se guarda en mayúsculas y sin acentos para
            emparejar igual que al aprender.
          </p>
        </div>
      )}

      <div className="mt-4 flex items-center gap-2">
        <input
          placeholder="Buscar por texto, etiqueta o categoría…"
          value={busqueda}
          onChange={(e) => setBusqueda(e.target.value)}
          className="w-72 rounded-lg border border-slate-300 px-3 py-1.5 text-sm"
        />
        <span className="text-sm text-slate-500">
          {items.length === 0
            ? 'Todavía no ha aprendido nada'
            : `${items.length} regla(s)`}
        </span>
      </div>

      <ul className="mt-3 space-y-2">
        {visibles.map((r) => (
          <li key={r.id} className="rounded-xl border border-slate-200 bg-white p-3">
            {editando === r.id ? (
              <div className="grid gap-2 sm:grid-cols-3">
                <input
                  value={edicion.patron}
                  onChange={(e) => setEdicion((f) => ({ ...f, patron: e.target.value }))}
                  className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
                />
                <select
                  value={edicion.categoria_id}
                  onChange={(e) => setEdicion((f) => ({ ...f, categoria_id: e.target.value, etiqueta_id: '' }))}
                  className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
                >
                  <option value="">Categoría…</option>
                  {categorias.map((c) => (
                    <option key={c.id} value={c.id}>{c.nombre}</option>
                  ))}
                </select>
                <select
                  value={edicion.etiqueta_id}
                  onChange={(e) => setEdicion((f) => ({ ...f, etiqueta_id: e.target.value }))}
                  className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
                >
                  <option value="">Etiqueta…</option>
                  {etqDeCategoria(edicion.categoria_id).map((e) => (
                    <option key={e.id} value={e.id}>{e.nombre}</option>
                  ))}
                </select>
                <div className="flex gap-2 sm:col-span-3">
                  <button
                    onClick={() => guardarEdicion(r.id)}
                    disabled={!edicion.etiqueta_id}
                    className="rounded-lg bg-indigo-600 px-3 py-1.5 text-sm text-white hover:bg-indigo-700 disabled:bg-slate-300"
                  >
                    Guardar
                  </button>
                  <button
                    onClick={() => setEditando(null)}
                    className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-50"
                  >
                    Cancelar
                  </button>
                </div>
              </div>
            ) : (
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <p className="font-medium text-slate-800">{r.patron}</p>
                  <p className="text-sm text-slate-500">
                    → {r.categoria_nombre ?? '—'} › {r.etiqueta_nombre ?? '—'}
                    <span className="ml-2 text-xs text-slate-400">
                      usada {r.veces_usada} vez(ces) · {r.actualizada_en.slice(0, 10)}
                    </span>
                  </p>
                </div>
                <div className="flex items-center gap-3">
                  <button onClick={() => abrirEditar(r)} className="text-sm text-indigo-600 hover:underline">
                    Corregir
                  </button>
                  <button onClick={() => eliminar(r)} className="text-sm text-red-600 hover:underline">
                    Borrar
                  </button>
                </div>
              </div>
            )}
          </li>
        ))}
        {items.length > 0 && visibles.length === 0 && (
          <li className="text-sm text-slate-400">Ninguna regla coincide con «{busqueda}»</li>
        )}
        {items.length === 0 && (
          <li className="rounded-xl border border-dashed border-slate-300 p-4 text-sm text-slate-500">
            Aquí aparecerá lo que aprenda. Para enseñarle algo: sube un recibo en{' '}
            <strong>Facturas</strong>, corrige la etiqueta de una línea y vuelve — o pulsa
            «Enseñar una regla».
          </li>
        )}
      </ul>
    </div>

    {/* Plantillas por emisor: no se puede ir a cada banco a pedirle un formato, pero la app se
        aprende el de cada uno. */}
    <div className="mt-6 rounded-xl border border-slate-200 bg-white p-4">
      <h2 className="font-medium text-slate-800">Plantillas por emisor</h2>
      <p className="mt-1 text-sm text-slate-500">
        Cuando corriges el monto o la fecha de una factura, Konta se aprende <strong>dónde
        venían</strong> en los documentos de ese emisor, y la próxima factura suya sale bien a la
        primera. Si borras una plantilla, esa casa se vuelve a leer adivinando.
      </p>
      <ul className="mt-3 space-y-2">
        {plantillas.map((p) => (
          <li
            key={p.id}
            className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-slate-200 p-3"
          >
            <div>
              <p className="font-medium text-slate-800">{p.nombre}</p>
              <p className="text-sm text-slate-500">
                {p.campo_monto ? (
                  <>
                    total en <span className="font-mono text-xs">{p.campo_monto}</span>
                  </>
                ) : (
                  'total: sin aprender'
                )}
                {p.campo_fecha ? (
                  <>
                    {' · '}fecha en <span className="font-mono text-xs">{p.campo_fecha}</span>
                  </>
                ) : null}
                {p.tipo_documento ? <> · {p.tipo_documento}</> : null}
                <span className="ml-2 text-xs text-slate-400">
                  usada {p.usos} vez(ces) · {p.actualizada_en.slice(0, 10)}
                </span>
              </p>
            </div>
            <button
              onClick={() => void borrarPlantilla(p.id)}
              className="text-sm text-red-600 hover:underline"
            >
              Borrar
            </button>
          </li>
        ))}
        {plantillas.length === 0 && (
          <li className="rounded-xl border border-dashed border-slate-300 p-4 text-sm text-slate-500">
            Todavía no ha aprendido ninguna. Corrige el monto de una factura en{' '}
            <strong>Facturas</strong> (✏️ Corregir) y aparecerá aquí.
          </li>
        )}
      </ul>
    </div>

    {/* Renglones que no son artículos: se aprenden de lo que el usuario borra. */}
    <div className="mt-6 rounded-xl border border-slate-200 bg-white p-4">
      <h2 className="font-medium text-slate-800">Renglones que no son artículos</h2>
      <p className="mt-1 text-sm text-slate-500">
        Recibos y facturas traen renglones que parecen productos pero no lo son (el NIT, el
        cajero, el cambio, el IVA). Konta ya descarta los más comunes, y aprende los demás
        cuando los borras: <strong>a la segunda vez</strong> deja de proponerlos.
      </p>
      <ul className="mt-3 space-y-2">
        {patrones.map((pat) => (
          <li
            key={pat.id}
            className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-slate-200 p-3"
          >
            <div>
              <p className="font-mono text-sm text-slate-800">{pat.patron}</p>
              <p className="text-xs text-slate-500">
                descartado {pat.veces} vez(ces) · lo que borraste: «{pat.ejemplo}»
              </p>
            </div>
            <button
              onClick={() => void borrarPatron(pat.id)}
              className="text-sm text-red-600 hover:underline"
            >
              Volver a tenerlo en cuenta
            </button>
          </li>
        ))}
        {patrones.length === 0 && (
          <li className="rounded-xl border border-dashed border-slate-300 p-4 text-sm text-slate-500">
            Todavía no has borrado ningún renglón repetido. Los del documento (NIT, cajero,
            cambio, IVA, totales) ya se descartan siempre.
          </li>
        )}
      </ul>
    </div>
    </>
  )
}
