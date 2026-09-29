import { useEffect, useState, type ChangeEvent } from 'react'
import { Link } from 'react-router-dom'
import { api, apiUpload } from '../api'
import SelectBuscable, { type Opcion } from '../components/SelectBuscable'
import {
  fmtMoney,
  type Categoria,
  type Cuenta,
  type Etiqueta,
  type Factura,
  type FacturaDetalle,
  type FacturaLinea,
  type SaldoResumen,
  type Tarjeta,
  type Transaccion,
} from '../types'

type SembradoDiccionario = { total_creadas: number; creadas: Etiqueta[] }

/** Color del badge según de dónde salió la clasificación de la línea. */
const ORIGEN: Record<string, { label: string; clase: string }> = {
  historial: { label: 'historial', clase: 'bg-emerald-100 text-emerald-700' },
  diccionario: { label: 'diccionario', clase: 'bg-sky-100 text-sky-700' },
  embeddings: { label: 'embeddings', clase: 'bg-violet-100 text-violet-700' },
  manual: { label: 'manual', clase: 'bg-indigo-100 text-indigo-700' },
  sin_clasificar: { label: 'sin clasificar', clase: 'bg-amber-100 text-amber-700' },
}

export default function Facturas() {
  const [items, setItems] = useState<Factura[]>([])
  const [transacciones, setTransacciones] = useState<Transaccion[]>([])
  const [categorias, setCategorias] = useState<Categoria[]>([])
  const [etiquetas, setEtiquetas] = useState<Etiqueta[]>([])
  const [cuentas, setCuentas] = useState<Cuenta[]>([])
  const [tarjetas, setTarjetas] = useState<Tarjeta[]>([])
  const [detalles, setDetalles] = useState<Record<string, FacturaDetalle>>({})
  const [cuentaSel, setCuentaSel] = useState<Record<string, string>>({})
  const [tarjetaSel, setTarjetaSel] = useState<Record<string, string>>({})
  const [fechaSel, setFechaSel] = useState<Record<string, string>>({})
  const [bulkCat, setBulkCat] = useState<Record<string, string>>({})
  // Un solo gasto con el total (la otra forma de cerrar el recibo)
  const [unicoMonto, setUnicoMonto] = useState<Record<string, string>>({})
  const [unicoDesc, setUnicoDesc] = useState<Record<string, string>>({})
  const [bulkEtq, setBulkEtq] = useState<Record<string, string>>({})
  const [respaldoCat, setRespaldoCat] = useState<Record<string, string>>({})
  const [sel, setSel] = useState<Record<string, string>>({})
  const [subiendo, setSubiendo] = useState(false)
  const [ocupado, setOcupado] = useState('')
  const [error, setError] = useState('')
  const [aviso, setAviso] = useState('')

  async function cargar() {
    setItems(await api<Factura[]>('/facturas'))
    setTransacciones(await api<Transaccion[]>('/transacciones'))
  }

  useEffect(() => {
    Promise.all([
      cargar(),
      api<Categoria[]>('/categorias').then(setCategorias),
      api<Etiqueta[]>('/etiquetas').then(setEtiquetas),
      // `GET /cuentas` devuelve el resumen con totales: las cuentas van en `cuentas`
      api<SaldoResumen>('/cuentas').then((r) => setCuentas(r.cuentas)),
      api<Tarjeta[]>('/tarjetas').then(setTarjetas),
    ]).catch((e) => setError(e instanceof Error ? e.message : 'Error'))
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

  async function conOcupado(id: string, fn: () => Promise<void>) {
    setOcupado(id)
    setError('')
    try {
      await fn()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error')
    } finally {
      setOcupado('')
    }
  }

  /**
   * Recarga etiquetas y categorías.
   *
   * Hace falta después de leer líneas: el servidor **crea solo** las etiquetas del
   * diccionario que le falten, y si la lista de la página no se recarga, el selector no
   * encuentra la etiqueta recién asignada y una línea clasificada parece «Sin etiqueta».
   */
  async function recargarEtiquetas() {
    const [cs, es] = await Promise.all([
      api<Categoria[]>('/categorias'),
      api<Etiqueta[]>('/etiquetas'),
    ])
    setCategorias(cs)
    setEtiquetas(es)
  }

  /** Parte el texto en líneas, las clasifica y las guarda. */
  const leerLineas = (id: string) =>
    conOcupado(id, async () => {
      const detalle = await api<FacturaDetalle>(`/facturas/${id}/lineas`, {
        method: 'POST',
        body: JSON.stringify({}),
      })
      setDetalles((d) => ({ ...d, [id]: detalle }))
      await cargar()
      await recargarEtiquetas()
    })

  /** Muestra las líneas ya guardadas de una factura. */
  const verLineas = (id: string) =>
    conOcupado(id, async () => {
      const detalle = await api<FacturaDetalle>(`/facturas/${id}`)
      setDetalles((d) => ({ ...d, [id]: detalle }))
    })

  async function cambiarEtiqueta(facturaId: string, lineaId: string, etiquetaId: string) {
    const linea = await api<FacturaLinea>(`/facturas/${facturaId}/lineas/${lineaId}`, {
      method: 'PATCH',
      body: JSON.stringify({ etiqueta_id: etiquetaId || null }),
    })
    setDetalles((d) => ({
      ...d,
      [facturaId]: {
        ...d[facturaId],
        lineas: d[facturaId].lineas.map((l) => (l.id === lineaId ? linea : l)),
      },
    }))
  }

  const descartarLinea = (facturaId: string, lineaId: string) =>
    conOcupado(facturaId, async () => {
      await api(`/facturas/${facturaId}/lineas/${lineaId}`, { method: 'DELETE' })
      const detalle = await api<FacturaDetalle>(`/facturas/${facturaId}`)
      setDetalles((d) => ({ ...d, [facturaId]: detalle }))
    })

  /** Crea una transacción de gasto por cada línea pendiente. */
  /** Igual que en Transacciones: el débito llena su cuenta; el crédito la limpia. */
  function elegirTarjeta(facturaId: string, tarjetaId: string) {
    setTarjetaSel((s) => ({ ...s, [facturaId]: tarjetaId }))
    const tarjeta = tarjetas.find((t) => t.id === tarjetaId)
    if (tarjeta?.tipo === 'debito' && tarjeta.cuenta_id) {
      setCuentaSel((s) => ({ ...s, [facturaId]: tarjeta.cuenta_id as string }))
    } else if (tarjeta?.tipo === 'credito') {
      setCuentaSel((s) => ({ ...s, [facturaId]: '' }))
    }
  }

  const confirmar = (facturaId: string) =>
    conOcupado(facturaId, async () => {
      const detalle = await api<FacturaDetalle>(`/facturas/${facturaId}/confirmar`, {
        method: 'POST',
        body: JSON.stringify({
          cuenta_id: cuentaSel[facturaId] || null,
          tarjeta_id: tarjetaSel[facturaId] || null,
          fecha: fechaSel[facturaId] || null,
          // Para las que sigan sin etiqueta: así no quedan gastos sin categoría
          categoria_id: respaldoCat[facturaId] || null,
        }),
      })
      setDetalles((d) => ({ ...d, [facturaId]: detalle }))
      await cargar()
    })

  /** Cierra el recibo como **una sola** transacción con el total. */
  const confirmarTotal = (facturaId: string) =>
    conOcupado(facturaId, async () => {
      const detalle = await api<FacturaDetalle>(`/facturas/${facturaId}/confirmar-total`, {
        method: 'POST',
        body: JSON.stringify({
          cuenta_id: cuentaSel[facturaId] || null,
          tarjeta_id: tarjetaSel[facturaId] || null,
          fecha: fechaSel[facturaId] || null,
          categoria_id: respaldoCat[facturaId] || null,
          // Vacío = que el servidor sume las líneas pendientes
          monto: unicoMonto[facturaId] || null,
          descripcion: unicoDesc[facturaId] || null,
        }),
      })
      setDetalles((d) => ({ ...d, [facturaId]: detalle }))
      setAviso('Recibo confirmado como un solo gasto (las líneas quedan como detalle).')
      await cargar()
    })

  /** Junta una factura confirmada línea por línea en **un** movimiento. */
  const unificar = (facturaId: string) =>
    conOcupado(facturaId, async () => {
      await api(`/facturas/${facturaId}/unificar`, { method: 'POST' })
      setAviso('Unificada en un solo movimiento (los artículos quedan como detalle).')
      const detalle = await api<FacturaDetalle>(`/facturas/${facturaId}`)
      setDetalles((d) => ({ ...d, [facturaId]: detalle }))
      await cargar()
    })

  /** Asigna una etiqueta a todas las líneas sin clasificar de una vez. */
  const asignarEnBloque = (facturaId: string) =>
    conOcupado(facturaId, async () => {
      const detalle = await api<FacturaDetalle>(`/facturas/${facturaId}/lineas`, {
        method: 'PATCH',
        body: JSON.stringify({
          etiqueta_id: bulkEtq[facturaId] || null,
          solo_sin_clasificar: true,
        }),
      })
      setDetalles((d) => ({ ...d, [facturaId]: detalle }))
      setAviso('Etiqueta aplicada a las líneas sin clasificar (y aprendida para la próxima).')
    })

  /** Siembra las etiquetas que el diccionario del OCR reconoce y vuelve a leer. */
  const prepararDiccionario = (facturaId: string) =>
    conOcupado(facturaId, async () => {
      const r = await api<SembradoDiccionario>('/etiquetas/diccionario', { method: 'POST' })
      await recargarEtiquetas()
      setEtiquetas(await api<Etiqueta[]>('/etiquetas'))
      await leerLineas(facturaId)
      setAviso(
        r.total_creadas > 0
          ? `✅ Creadas ${r.total_creadas} etiqueta(s) del diccionario.`
          : 'Sin etiquetas nuevas: revisa que existan las categorías Mercado, Transporte y Otros gastos.',
      )
    })

  async function asociar(facturaId: string) {
    const txId = sel[facturaId]
    if (!txId) return
    const r = await api<{ aviso: string | null }>(`/facturas/${facturaId}/asociar`, {
      method: 'POST',
      body: JSON.stringify({ transaccion_id: txId }),
    })
    setAviso(r.aviso ?? '')
    const d = await api<FacturaDetalle>(`/facturas/${facturaId}`)
    setDetalles((prev) => ({ ...prev, [facturaId]: d }))
    cargar()
  }

  async function eliminar(id: string) {
    await api(`/facturas/${id}`, { method: 'DELETE' })
    setDetalles((d) => {
      const copia = { ...d }
      delete copia[id]
      return copia
    })
    cargar()
  }

  const descTx = (t: Transaccion) => `${t.fecha} · ${t.descripcion ?? t.tipo} · ${fmtMoney(t.monto)}`

  /** Etiquetas de una categoría, con sus subetiquetas indentadas. */
  function opcionesDeCategoria(c: Categoria) {
    const ops: { id: string; label: string }[] = []
    for (const raiz of etiquetas.filter((e) => e.categoria_id === c.id && !e.padre_id)) {
      ops.push({ id: raiz.id, label: raiz.nombre })
      for (const hija of etiquetas.filter((e) => e.padre_id === raiz.id)) {
        ops.push({ id: hija.id, label: `${raiz.nombre} › ${hija.nombre}` })
      }
    }
    return ops
  }

  /**
   * Lo que se muestra en la columna «Origen».
   *
   * Si la línea **no tiene etiqueta**, el origen es «sin clasificar» aunque el clasificador
   * hubiera dicho otra cosa: una fila con el badge azul de `diccionario` y el selector en
   * «Sin etiqueta» se contradice a sí misma.
   */
  function origenDe(linea: FacturaLinea) {
    if (!linea.etiqueta_id) return ORIGEN.sin_clasificar
    return ORIGEN[linea.origen] ?? ORIGEN.sin_clasificar
  }

  /** Todas las etiquetas en una lista plana con su categoría, para el buscador. */
  const opcionesEtiquetas: Opcion[] = categorias.flatMap((c) =>
    opcionesDeCategoria(c).map((o) => ({ ...o, grupo: c.nombre }))
  )

  const totalDe = (lineas: FacturaLinea[]) =>
    lineas.reduce((acc, l) => acc + Number(l.valor_total), 0)

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-xl font-semibold">Facturas (PDF)</h2>
        <Link to="/reglas-ocr" className="text-sm text-indigo-600 hover:underline">
          Ver lo que el OCR ha aprendido →
        </Link>
      </div>
      {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
      {aviso && <p className="mt-2 text-sm text-emerald-700">{aviso}</p>}

      <div className="mt-4 rounded-xl border border-slate-200 bg-white p-5">
        <p className="text-sm text-slate-600">
          Sube una factura en PDF o una <strong>foto del recibo</strong> (JPG/PNG). Se extrae el
          texto (con OCR si es escaneada), se detectan el monto y la fecha, y con{' '}
          <strong>Leer líneas</strong> se parte en artículos: uno por transacción.
        </p>
        <input
          type="file"
          accept="application/pdf,image/*"
          onChange={subir}
          disabled={subiendo}
          className="mt-3 block w-full text-sm text-slate-600 file:mr-4 file:rounded-lg file:border-0 file:bg-indigo-600 file:px-4 file:py-2 file:text-sm file:font-medium file:text-white hover:file:bg-indigo-700"
        />
        {subiendo && <p className="mt-2 text-sm text-slate-500">Procesando el archivo…</p>}
      </div>

      <ul className="mt-4 space-y-3">
        {items.map((f) => {
          const detalle = detalles[f.id]
          const pendientes = detalle?.lineas.filter((l) => !l.transaccion_id) ?? []
          return (
            <li key={f.id} className="rounded-xl border border-slate-200 bg-white p-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="font-medium">{f.nombre_archivo}</p>
                  <p className="text-sm text-slate-500">
                    Monto detectado:{' '}
                    <span className="font-medium text-slate-700">
                      {f.monto_detectado != null ? fmtMoney(f.monto_detectado) : '—'}
                    </span>
                    {' · '}Fecha: {f.fecha_detectada ?? '—'}
                  </p>
                  {f.transaccion_id ? (
                    detalle && detalle.descuadre != null && Number(detalle.descuadre) !== 0 ? (
                      <p className="mt-1 text-xs text-red-600">
                        ✗ No cuadra: factura {fmtMoney(f.monto_detectado)} vs transacción{' '}
                        {fmtMoney(detalle.transaccion_monto)}
                      </p>
                    ) : (
                      <p className="mt-1 text-xs text-emerald-600">
                        ✓ Asociada{detalle?.transaccion_monto != null ? ` y cuadra con ${fmtMoney(detalle.transaccion_monto)}` : ''}
                      </p>
                    )
                  ) : (
                    <p className="mt-1 text-xs text-amber-600">Sin asociar</p>
                  )}
                </div>
                <div className="flex shrink-0 items-center gap-3">
                  <button
                    onClick={() => leerLineas(f.id)}
                    disabled={ocupado === f.id}
                    className="rounded-lg bg-indigo-600 px-3 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
                  >
                    {ocupado === f.id ? 'Leyendo…' : 'Leer líneas'}
                  </button>
                  <button
                    onClick={() => verLineas(f.id)}
                    className="text-sm text-slate-600 hover:underline"
                  >
                    Ver líneas
                  </button>
                  <button onClick={() => eliminar(f.id)} className="text-sm text-red-600 hover:underline">
                    Eliminar
                  </button>
                </div>
              </div>

              {detalle && (
                <div className="mt-3 rounded-lg border border-slate-200 bg-slate-50 p-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="text-sm text-slate-600">
                      <strong>{detalle.lineas.length}</strong> línea(s)
                      {detalle.tipo_documento ? ` · ${detalle.tipo_documento}` : ''} · total{' '}
                      <strong className="text-slate-800">{fmtMoney(totalDe(detalle.lineas))}</strong>
                      {pendientes.length > 0 && ` · ${pendientes.length} sin confirmar`}
                      {(() => {
                        const confirmadas = detalle.lineas.filter((li) => li.transaccion_id)
                        const ids = new Set(confirmadas.map((li) => li.transaccion_id))
                        return confirmadas.length > 1 && ids.size === 1
                          ? ' · confirmado como un solo gasto'
                          : ''
                      })()}
                    </p>
                    {pendientes.length > 0 && (
                      <div className="flex flex-wrap items-center gap-2">
                        <select
                          value={tarjetaSel[f.id] ?? ''}
                          onChange={(e) => elegirTarjeta(f.id, e.target.value)}
                          className="rounded-lg border border-slate-300 px-2 py-1.5 text-sm"
                        >
                          <option value="">Sin tarjeta</option>
                          {tarjetas.map((t) => (
                            <option key={t.id} value={t.id}>
                              💳 {t.nombre} ({t.tipo})
                            </option>
                          ))}
                        </select>
                        <select
                          value={cuentaSel[f.id] ?? ''}
                          onChange={(e) => setCuentaSel((s) => ({ ...s, [f.id]: e.target.value }))}
                          className="rounded-lg border border-slate-300 px-2 py-1.5 text-sm"
                        >
                          <option value="">Sin cuenta</option>
                          {cuentas.map((c) => (
                            <option key={c.id} value={c.id}>
                              {c.nombre}
                            </option>
                          ))}
                        </select>
                        <input
                          type="date"
                          value={fechaSel[f.id] ?? f.fecha_detectada ?? ''}
                          onChange={(e) => setFechaSel((s) => ({ ...s, [f.id]: e.target.value }))}
                          title="Fecha de la compra"
                          className="rounded-lg border border-slate-300 px-2 py-1.5 text-sm"
                        />
                        <button
                          onClick={() => confirmarTotal(f.id)}
                          disabled={ocupado === f.id}
                          title="Un solo movimiento con los artículos como detalle (recomendado para el mercado)"
                          className="rounded-lg bg-emerald-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-emerald-700 disabled:opacity-50"
                        >
                          Registrar la compra
                        </button>
                        <button
                          onClick={() => confirmar(f.id)}
                          disabled={ocupado === f.id}
                          className="text-xs text-slate-500 underline hover:text-slate-700"
                        >
                          o separar en {pendientes.length} movimientos
                        </button>
                      </div>
                    )}
                    {pendientes.length === 0 &&
                      detalle.lineas.length > 0 &&
                      new Set(detalle.lineas.map((l) => l.transaccion_id)).size !== 1 && (
                        <div className="flex flex-wrap items-center gap-2">
                          <button
                            onClick={() => unificar(f.id)}
                            disabled={ocupado === f.id}
                            title="Junta los movimientos por artículo en una sola compra (los artículos quedan como detalle)"
                            className="rounded-lg border border-indigo-200 bg-indigo-50 px-3 py-1.5 text-sm text-indigo-700 hover:bg-indigo-100 disabled:opacity-50"
                          >
                            Unificar en un solo movimiento
                          </button>
                        </div>
                      )}
                    {pendientes.some((l) => l.origen === 'sin_clasificar') && (
                      <div className="mt-3 flex flex-wrap items-end gap-2 rounded-lg border border-slate-200 bg-white p-2">
                        <span className="text-xs text-slate-500">
                          Asignar a las {pendientes.filter((l) => l.origen === 'sin_clasificar').length} sin
                          clasificar:
                        </span>
                        <select
                          value={bulkCat[f.id] ?? ''}
                          onChange={(e) => {
                            const valor = e.target.value
                            setBulkCat((s) => ({ ...s, [f.id]: valor }))
                            setBulkEtq((s) => ({ ...s, [f.id]: '' }))
                          }}
                          className="rounded-lg border border-slate-300 px-2 py-1.5 text-sm"
                        >
                          <option value="">Categoría…</option>
                          {categorias.filter((c) => c.tipo === 'gasto').map((c) => (
                            <option key={c.id} value={c.id}>{c.nombre}</option>
                          ))}
                        </select>
                        <SelectBuscable
                          opciones={opcionesEtiquetas.filter((o) =>
                            bulkCat[f.id] ? o.grupo === categorias.find((c) => c.id === bulkCat[f.id])?.nombre : true
                          )}
                          value={bulkEtq[f.id] ?? ''}
                          onChange={(id) => setBulkEtq((s) => ({ ...s, [f.id]: id }))}
                          textoVacio="Etiqueta…"
                          placeholder="Buscar etiqueta…"
                        />
                        <button
                          onClick={() => asignarEnBloque(f.id)}
                          disabled={ocupado === f.id || !bulkEtq[f.id]}
                          className="rounded-lg border border-indigo-200 bg-indigo-50 px-3 py-1.5 text-sm text-indigo-700 hover:bg-indigo-100 disabled:opacity-50"
                        >
                          Aplicar
                        </button>
                        <span className="text-xs text-slate-400">
                          (se aprende: la próxima ya sale clasificada)
                        </span>
                      </div>
                    )}
                    {pendientes.length > 0 && pendientes.some((l) => l.origen === 'sin_clasificar') && (
                      <p className="mt-2 text-xs text-slate-500">
                        Las que sigan sin clasificar al confirmar: elige una{' '}
                        <select
                          value={respaldoCat[f.id] ?? ''}
                          onChange={(e) => setRespaldoCat((s) => ({ ...s, [f.id]: e.target.value }))}
                          className="rounded border border-slate-300 px-1 py-0.5 text-xs"
                        >
                          <option value="">categoría de respaldo</option>
                          {categorias.filter((c) => c.tipo === 'gasto').map((c) => (
                            <option key={c.id} value={c.id}>{c.nombre}</option>
                          ))}
                        </select>{' '}
                        para que el gasto no quede sin categoría (si no, no sale en reportes ni en
                        presupuestos).
                      </p>
                    )}
                    {tarjetaSel[f.id] && tarjetas.find((t) => t.id === tarjetaSel[f.id])?.tipo === 'credito' && (
                      <p className="mt-1 text-xs text-slate-500">
                        Es una tarjeta de <strong>crédito</strong>: el gasto no sale de la cuenta, se
                        suma a la deuda de la tarjeta.
                      </p>
                    )}
                    {detalle.lineas.some((l) => !l.transaccion_id && l.origen === 'sin_clasificar') && (
                      <button
                        onClick={() => prepararDiccionario(f.id)}
                        disabled={ocupado === f.id}
                        className="mt-2 rounded-lg border border-indigo-200 bg-indigo-50 px-3 py-1.5 text-sm text-indigo-700 hover:bg-indigo-100 disabled:opacity-50"
                      >
                        Preparar etiquetas del diccionario y volver a clasificar
                      </button>
                    )}

                    {pendientes.length > 0 && (
                      <div className="mt-3 rounded-lg border border-slate-200 bg-slate-50 p-2">
                        <p className="text-xs text-slate-500">
                          <strong>Registrar la compra</strong>: un solo movimiento con el total y los{' '}
                          {pendientes.length} artículos guardados como detalle (recomendado para el
                          mercado). Cambia la descripción o el total si lo necesitas.
                        </p>
                        <div className="mt-1 flex flex-wrap items-center gap-2">
                          <input
                            placeholder="Descripción (ej. Ropa de temporada)"
                            value={unicoDesc[f.id] ?? ''}
                            onChange={(e) => setUnicoDesc((s) => ({ ...s, [f.id]: e.target.value }))}
                            className="w-56 rounded-lg border border-slate-300 px-2 py-1.5 text-sm"
                          />
                          <input
                            placeholder={fmtMoney(pendientes.reduce((a, li) => a + Number(li.valor_total), 0))}
                            value={unicoMonto[f.id] ?? ''}
                            onChange={(e) => setUnicoMonto((s) => ({ ...s, [f.id]: e.target.value }))}
                            className="w-32 rounded-lg border border-slate-300 px-2 py-1.5 text-sm"
                          />
                          <button
                            onClick={() => confirmarTotal(f.id)}
                            disabled={ocupado === f.id}
                            className="rounded-lg bg-emerald-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-emerald-700 disabled:opacity-50"
                          >
                            Registrar la compra
                          </button>
                          {f.monto_detectado != null &&
                            Number(f.monto_detectado) !==
                              pendientes.reduce((a, li) => a + Number(li.valor_total), 0) && (
                              <button
                                onClick={() =>
                                  setUnicoMonto((s) => ({ ...s, [f.id]: String(f.monto_detectado) }))
                                }
                                className="text-xs text-indigo-600 hover:underline"
                              >
                                usar el total del recibo ({fmtMoney(f.monto_detectado)})
                              </button>
                            )}
                        </div>
                      </div>
                    )}
                  </div>

                  {detalle.lineas.length > 0 ? (
                    <div className="mt-2 overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="text-left text-xs uppercase tracking-wide text-slate-500">
                            <th className="py-1 pr-3">Artículo</th>
                            <th className="py-1 pr-3">Valor</th>
                            <th className="py-1 pr-3">Etiqueta</th>
                            <th className="py-1 pr-3">Origen</th>
                            <th className="py-1" />
                          </tr>
                        </thead>
                        <tbody>
                          {detalle.lineas.map((l) => (
                            <tr key={l.id} className="border-t border-slate-200">
                              <td className="py-2 pr-3">
                                <span className="text-slate-700">{l.descripcion}</span>
                                {l.cantidad != null && (
                                  <span className="ml-2 text-xs text-slate-500">
                                    {Number(l.cantidad)} ×{' '}
                                    {l.valor_unitario != null ? fmtMoney(l.valor_unitario) : '—'}
                                  </span>
                                )}
                              </td>
                              <td className="py-2 pr-3 whitespace-nowrap font-medium text-slate-700">
                                {fmtMoney(l.valor_total)}
                              </td>
                              <td className="py-2 pr-3">
                                <SelectBuscable
                                  opciones={opcionesEtiquetas}
                                  value={l.etiqueta_id ?? ''}
                                  onChange={(id) => cambiarEtiqueta(f.id, l.id, id)}
                                  disabled={!!l.transaccion_id}
                                  className="max-w-[16rem]"
                                />
                              </td>
                              <td className="py-2 pr-3">
                                {l.transaccion_id ? (
                                  <span className="rounded bg-emerald-100 px-2 py-0.5 text-xs text-emerald-700">
                                    confirmada
                                  </span>
                                ) : (
                                  <span
                                    className={`rounded px-2 py-0.5 text-xs ${origenDe(l).clase}`}
                                    title={
                                      l.confianza != null ? `confianza ${l.confianza}` : undefined
                                    }
                                  >
                                    {origenDe(l).label}
                                  </span>
                                )}
                              </td>
                              <td className="py-2 text-right">
                                {!l.transaccion_id && (
                                  <button
                                    onClick={() => descartarLinea(f.id, l.id)}
                                    className="text-xs text-red-600 hover:underline"
                                    title="Descartar esta línea"
                                  >
                                    ✕
                                  </button>
                                )}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <p className="mt-2 text-sm text-slate-500">
                      No se detectaron artículos. Prueba con una foto más nítida o revisa el texto
                      extraído.
                    </p>
                  )}
                </div>
              )}

              {!f.transaccion_id && transacciones.length > 0 && (
                <div className="mt-3 flex flex-wrap items-center gap-2">
                  <select
                    value={sel[f.id] ?? ''}
                    onChange={(e) => setSel((s) => ({ ...s, [f.id]: e.target.value }))}
                    className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
                  >
                    <option value="">Asociar a transacción…</option>
                    {transacciones.slice(0, 50).map((t) => (
                      <option key={t.id} value={t.id}>
                        {descTx(t)}
                      </option>
                    ))}
                  </select>
                  <button
                    onClick={() => asociar(f.id)}
                    className="rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-700 hover:bg-slate-50"
                  >
                    Asociar
                  </button>
                </div>
              )}

              {f.texto_extraido && (
                <details className="mt-3">
                  {/* El texto se muestra **entero**. Antes se cortaba en 1.500 caracteres y
                      parecía que el OCR solo había leído una parte de la factura. */}
                  <summary className="cursor-pointer text-sm text-slate-500">
                    Ver texto extraído ({f.texto_extraido.length.toLocaleString('es-CO')}{' '}
                    caracteres)
                  </summary>
                  <div className="mt-2 flex flex-wrap items-center gap-3">
                    <button
                      onClick={() => {
                        void navigator.clipboard?.writeText(f.texto_extraido ?? '')
                        setAviso('Texto copiado al portapapeles.')
                      }}
                      className="rounded-lg border border-slate-300 px-3 py-1 text-xs text-slate-700 hover:bg-slate-50"
                    >
                      Copiar todo
                    </button>
                    <span className="text-xs text-slate-500">
                      Es el texto completo que leyó Konta, no un fragmento.
                    </span>
                  </div>
                  <pre className="mt-2 max-h-72 overflow-auto whitespace-pre-wrap rounded-lg bg-slate-50 p-3 text-xs text-slate-600">
                    {f.texto_extraido}
                  </pre>
                </details>
              )}
            </li>
          )
        })}
        {items.length === 0 && <p className="text-sm text-slate-500">Aún no has subido facturas.</p>}
      </ul>
    </div>
  )
}
