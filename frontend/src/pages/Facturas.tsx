import { useEffect, useRef, useState, type ChangeEvent } from 'react'
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
  // El archivo se guarda (no se sube al elegirlo) para poder escribir la contraseña del PDF
  const [archivo, setArchivo] = useState<File | null>(null)
  const [contrasena, setContrasena] = useState('')
  // Texto que el usuario está corrigiendo (por factura). Es el paracaídas del lector: si el
  // OCR o la extracción se equivocan, se arregla el texto y se vuelve a leer.
  const [textoEditando, setTextoEditando] = useState<Record<string, string>>({})
  // Corrección del monto y la fecha que detectó el lector (por factura)
  const [datosEditando, setDatosEditando] = useState<string | null>(null)
  const [montoEditado, setMontoEditado] = useState<Record<string, string>>({})
  const [fechaEditada, setFechaEditada] = useState<Record<string, string>>({})
  // Artículo que el usuario añade a mano (el lector se lo saltó)
  const [agregando, setAgregando] = useState<string | null>(null)
  const [nuevaLinea, setNuevaLinea] = useState<Record<string, { descripcion: string; valor: string; etiqueta: string }>>({})
  const [corrigiendoTexto, setCorrigiendoTexto] = useState<string | null>(null)
  const entradaArchivo = useRef<HTMLInputElement>(null)
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

  async function subir(elegido?: File) {
    // Se le pasa el archivo **recién elegido** desde el input: `setArchivo` no se aplica
    // hasta el siguiente render, así que leer el estado aquí subiría el archivo anterior.
    const file = elegido ?? archivo
    if (!file) {
      setError('Elige el archivo de la factura (PDF o foto)')
      return
    }
    setSubiendo(true)
    setError('')
    setAviso('')
    try {
      const fd = new FormData()
      fd.append('archivo', file)
      // Las facturas electrónicas suelen venir en PDF protegido (la clave es el NIT del
      // emisor). Si el PDF no está protegido, la contraseña se ignora.
      if (contrasena) fd.append('contrasena', contrasena)
      const subida = await apiUpload<Factura>('/facturas', fd)
      // Decir siempre el resultado y el paso siguiente: antes, si todo iba bien, no se decía
      // nada y no había forma de saber si la subida había entrado.
      const leyo = (subida.texto_extraido ?? '').trim().length > 0
      setAviso(
        subida.duplicada
          ? '⚠ Esa factura ya la habías subido (mismo CUDE de la DIAN). Revísala antes de confirmarla.'
          : leyo
            ? '✅ Subida. Pulsa «Leer líneas» en la factura para partirla en artículos.'
            : '⚠ Subida, pero no se pudo leer texto. Prueba con una foto más nítida o un PDF.'
      )
      setArchivo(null)
      setContrasena('')
      if (entradaArchivo.current) entradaArchivo.current.value = ''
      await cargar()
    } catch (err) {
      // Se conserva el archivo y la contraseña: casi siempre es que hay que corregirla
      setError(err instanceof Error ? err.message : 'Error al subir la factura')
    } finally {
      setSubiendo(false)
    }
  }

  /** Corrige el monto y la fecha que detectó el lector. */
  const guardarDatos = (facturaId: string) =>
    conOcupado(facturaId, async () => {
      const detalle = await api<FacturaDetalle>(`/facturas/${facturaId}`, {
        method: 'PATCH',
        body: JSON.stringify({
          monto_detectado: montoEditado[facturaId] || null,
          fecha_detectada: fechaEditada[facturaId] || null,
        }),
      })
      setDetalles((d) => ({ ...d, [facturaId]: detalle }))
      setDatosEditando(null)
      setAviso('✅ Monto y fecha corregidos (la auditoría y «Registrar el gasto» usan el monto bueno).')
      await cargar()
    })

  /** Añade a mano un artículo que el lector se saltó. */
  const agregarLinea = (facturaId: string) =>
    conOcupado(facturaId, async () => {
      const campos = nuevaLinea[facturaId] ?? { descripcion: '', valor: '', etiqueta: '' }
      const detalle = await api<FacturaDetalle>(`/facturas/${facturaId}/lineas/agregar`, {
        method: 'POST',
        body: JSON.stringify({
          descripcion: campos.descripcion.trim(),
          valor_total: campos.valor.replace(/[^\d.]/g, '') || '0',
          etiqueta_id: campos.etiqueta || null,
        }),
      })
      setDetalles((d) => ({ ...d, [facturaId]: detalle }))
      setAgregando(null)
      setNuevaLinea((s) => ({ ...s, [facturaId]: { descripcion: '', valor: '', etiqueta: '' } }))
      setAviso('✅ Artículo añadido (queda como manual: un re-leer no se lo lleva).')
      await cargar()
    })

  /** Sube o baja una línea en el orden de la factura. */
  const moverLinea = (facturaId: string, lineaId: string, salto: number) => {
    const detalle = detalles[facturaId]
    if (!detalle) return
    const ids = detalle.lineas.map((l) => l.id)
    const desde = ids.indexOf(lineaId)
    const hasta = desde + salto
    if (desde < 0 || hasta < 0 || hasta >= ids.length) return
    ;[ids[desde], ids[hasta]] = [ids[hasta], ids[desde]]
    return conOcupado(facturaId, async () => {
      const nuevo = await api<FacturaDetalle>(`/facturas/${facturaId}/lineas/orden`, {
        method: 'PUT',
        body: JSON.stringify({ linea_ids: ids }),
      })
      setDetalles((d) => ({ ...d, [facturaId]: nuevo }))
    })
  }

  /** Guarda el texto corregido y vuelve a leer la factura con él. */
  const guardarTextoYLeer = (facturaId: string) =>
    conOcupado(facturaId, async () => {
      const detalle = await api<FacturaDetalle>(`/facturas/${facturaId}/lineas`, {
        method: 'POST',
        body: JSON.stringify({ texto: textoEditando[facturaId] ?? '' }),
      })
      setDetalles((d) => ({ ...d, [facturaId]: detalle }))
      setCorrigiendoTexto(null)
      setAviso('✅ Se volvió a leer con tu texto (y se re-detectaron el monto y la fecha).')
      await cargar()
    })

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
      // Si la factura ya está dentro de un movimiento, se avisa antes: el backend **no**
      // duplica las líneas ya registradas, pero es una acción que toca datos ya cuadrados.
      const enMovimiento = items.find((f) => f.id === id)?.transaccion_id
      const registradas = (detalles[id]?.lineas ?? []).filter((li) => li.transaccion_id).length
      if (enMovimiento || registradas > 0) {
        const seguir = window.confirm(
          'Esta factura ya está registrada en un movimiento.\n\n' +
            'Se volverán a leer las líneas. Las que ya están registradas **no** se duplican, ' +
            'pero los cambios que hayas hecho a mano pueden perderse. ¿Seguir?'
        )
        if (!seguir) return
      }
      const detalle = await api<FacturaDetalle>(`/facturas/${id}/lineas`, {
        method: 'POST',
        body: JSON.stringify({}),
      })
      setDetalles((d) => ({ ...d, [id]: detalle }))
      if (detalle.aviso) setAviso(`ℹ️ ${detalle.aviso}`)
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

  /** Categoría/etiqueta que se proponen para un recibo de servicio (parqueadero). */
  function sugeridas(detalle: FacturaDetalle) {
    if (detalle.tipo_documento === 'parqueadero') {
      return {
        categoria: categorias.find((c) => c.nombre === 'Transporte')?.id ?? '',
        etiqueta: etiquetas.find((e) => e.nombre === 'Parqueadero')?.id ?? '',
      }
    }
    return { categoria: '', etiqueta: '' }
  }

  /** Un recibo **sin artículos** (parqueadero, factura de servicios): un solo gasto. */
  const registrarServicio = (facturaId: string, detalle: FacturaDetalle) => {
    const sug = sugeridas(detalle)
    return conOcupado(facturaId, async () => {
      const d = await api<FacturaDetalle>(`/facturas/${facturaId}/confirmar-total`, {
        method: 'POST',
        body: JSON.stringify({
          cuenta_id: cuentaSel[facturaId] || null,
          tarjeta_id: tarjetaSel[facturaId] || null,
          fecha: fechaSel[facturaId] || null,
          // `||` y no `??`: con `??`, una cadena vacía se mantiene y se enviaba
          // `categoria_id: ""`, que no es un UUID y devolvía 422 al registrar el gasto.
          categoria_id: respaldoCat[facturaId] || sug.categoria || null,
          etiqueta_id: bulkEtq[facturaId] || sug.etiqueta || null,
        }),
      })
      setDetalles((prev) => ({ ...prev, [facturaId]: d }))
      setAviso('Gasto registrado desde el recibo.')
      await cargar()
    })
  }

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

  /**
   * Etiquetas de una categoría con **todo** su árbol, indentadas.
   *
   * Antes solo bajaba dos niveles, así que una subetiqueta de tercero (por ejemplo
   * `Suscripciones › Streaming › Netflix`) no se podía elegir aunque la app la guarde y los
   * reportes agrupen por esa ruta.
   */
  function opcionesDeCategoria(c: Categoria) {
    const ops: { id: string; label: string }[] = []
    const hijas = (padreId: string | null, prefijo: string) => {
      for (const e of etiquetas.filter((x) => x.categoria_id === c.id && x.padre_id === padreId)) {
        ops.push({ id: e.id, label: `${prefijo}${e.nombre}` })
        hijas(e.id, `${prefijo}${e.nombre} › `)
      }
    }
    hijas(null, '')
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
          ref={entradaArchivo}
          type="file"
          accept="application/pdf,image/*"
          onChange={(e: ChangeEvent<HTMLInputElement>) => {
            const elegido = e.target.files?.[0] ?? null
            setArchivo(elegido)
            setError('')
            setAviso('')
            // Sube al elegirlo (un solo paso). Si el PDF viene protegido, el aviso lo dice,
            // el archivo se queda elegido y solo hay que escribir la contraseña y pulsar
            // «Subir factura».
            if (elegido) void subir(elegido)
          }}
          disabled={subiendo}
          className="mt-3 block w-full text-sm text-slate-600 file:mr-4 file:rounded-lg file:border-0 file:bg-indigo-600 file:px-4 file:py-2 file:text-sm file:font-medium file:text-white hover:file:bg-indigo-700"
        />
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <input
            type="password"
            value={contrasena}
            onChange={(e) => setContrasena(e.target.value)}
            placeholder="Contraseña del PDF (si está protegido)"
            autoComplete="new-password"
            className="w-64 rounded-lg border border-slate-300 px-3 py-2 text-sm"
          />
          <button
            onClick={() => void subir()}
            disabled={subiendo || !archivo}
            className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
          >
            {subiendo ? 'Procesando…' : 'Volver a subir'}
          </button>
          <span className="text-xs text-slate-500">
            {archivo ? archivo.name : 'Ningún archivo seleccionado'}
          </span>
        </div>
        <p className="mt-2 text-xs text-slate-500">
          Si el PDF viene con contraseña (lo normal en una factura electrónica: suele ser el{' '}
          <strong>NIT del emisor</strong>), escríbela aquí antes de subir.
        </p>
      </div>

      <ul className="mt-4 space-y-3">
        {items.map((f) => {
          const detalle = detalles[f.id]
          const pendientes = detalle?.lineas.filter((l) => !l.transaccion_id) ?? []
          return (
            <li key={f.id} className="rounded-xl border border-slate-200 bg-white p-4">
              {/* `flex-wrap` y `min-w-0`: con un nombre de archivo largo, los botones
                  («Leer líneas») se salían de la tarjeta y en una pantalla estrecha no se
                  veían. Ahora bajan a la línea siguiente. */}
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="break-words font-medium">{f.nombre_archivo}</p>
                  <p className="text-sm text-slate-500">
                    Monto detectado:{' '}
                    <span className="font-medium text-slate-700">
                      {f.monto_detectado != null ? fmtMoney(f.monto_detectado) : '—'}
                    </span>
                    {' · '}Fecha: {f.fecha_detectada ?? '—'}
                    {datosEditando !== f.id && (
                      <button
                        onClick={() => {
                          setMontoEditado((s) => ({
                            ...s,
                            [f.id]: f.monto_detectado != null ? String(f.monto_detectado) : '',
                          }))
                          setFechaEditada((s) => ({ ...s, [f.id]: f.fecha_detectada ?? '' }))
                          setDatosEditando(f.id)
                        }}
                        className="ml-2 text-xs text-indigo-600 hover:underline"
                      >
                        ✏️ Corregir
                      </button>
                    )}
                  </p>
                  {datosEditando === f.id && (
                    <div className="mt-2 flex flex-wrap items-end gap-2 rounded-lg bg-slate-50 p-3">
                      <label className="text-xs text-slate-600">
                        Monto
                        <input
                          value={montoEditado[f.id] ?? ''}
                          onChange={(e) =>
                            setMontoEditado((s) => ({ ...s, [f.id]: e.target.value }))
                          }
                          inputMode="decimal"
                          placeholder="844041"
                          className="mt-1 block w-40 rounded-lg border border-slate-300 px-3 py-1.5 text-sm"
                        />
                      </label>
                      <label className="text-xs text-slate-600">
                        Fecha
                        <input
                          type="date"
                          value={fechaEditada[f.id] ?? ''}
                          onChange={(e) =>
                            setFechaEditada((s) => ({ ...s, [f.id]: e.target.value }))
                          }
                          className="mt-1 block rounded-lg border border-slate-300 px-3 py-1.5 text-sm"
                        />
                      </label>
                      <button
                        onClick={() => void guardarDatos(f.id)}
                        disabled={ocupado === f.id}
                        className="rounded-lg bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
                      >
                        {ocupado === f.id ? 'Guardando…' : 'Guardar'}
                      </button>
                      <button
                        onClick={() => setDatosEditando(null)}
                        className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm text-slate-700 hover:bg-white"
                      >
                        Cancelar
                      </button>
                      <span className="text-xs text-slate-500">
                        Déjalo vacío para borrarlo. Con esto la auditoría deja de marcar un
                        descuadre que no existe.
                      </span>
                    </div>
                  )}
                  {f.cude && (
                    <p className="mt-1 text-xs text-slate-400">
                      CUDE {f.cude.slice(0, 10)}…{' '}
                      {f.url_dian && (
                        <a
                          href={f.url_dian}
                          target="_blank"
                          rel="noreferrer"
                          className="text-indigo-600 hover:underline"
                        >
                          Ver en la DIAN ↗
                        </a>
                      )}
                    </p>
                  )}
                  {(detalle?.duplicada || f.duplicada) && (
                    <p className="mt-1 text-xs text-amber-600">
                      ⚠ Ya tienes otra factura con este mismo CUDE
                    </p>
                  )}
                  {f.transaccion_id ? (
                    detalle &&
                    detalle.descuadre != null &&
                    Math.abs(Number(detalle.descuadre)) > 1 ? (
                      <p className="mt-1 text-xs text-red-600">
                        ✗ No cuadra: factura {fmtMoney(f.monto_detectado)} vs transacción{' '}
                        {fmtMoney(detalle.transaccion_monto)}
                      </p>
                    ) : (
                      <p className="mt-1 text-xs text-emerald-600">
                        ✓ Asociada{detalle?.transaccion_monto != null ? ` y cuadra con ${fmtMoney(detalle.transaccion_monto)}` : ''}
                        {detalle?.descuadre != null && Number(detalle.descuadre) !== 0
                          ? ` (diferencia de ${fmtMoney(Math.abs(Number(detalle.descuadre)))}, redondeo del OCR)`
                          : ''}
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
                    {(pendientes.length > 0 || (detalle.lineas.length === 0 && !detalle.transaccion_id)) && (
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
                        {detalle.lineas.length === 0 ? (
                          <>
                            <select
                              value={respaldoCat[f.id] ?? sugeridas(detalle).categoria}
                              onChange={(e) => setRespaldoCat((s) => ({ ...s, [f.id]: e.target.value }))}
                              className="rounded-lg border border-slate-300 px-2 py-1.5 text-sm"
                            >
                              <option value="">Categoría…</option>
                              {categorias
                                .filter((c) => c.tipo === 'gasto')
                                .map((c) => (
                                  <option key={c.id} value={c.id}>{c.nombre}</option>
                                ))}
                            </select>
                            <SelectBuscable
                              opciones={opcionesEtiquetas.filter(
                                (o) =>
                                  o.grupo ===
                                  (categorias.find(
                                    (c) => c.id === (respaldoCat[f.id] ?? sugeridas(detalle).categoria)
                                  )?.nombre ?? '')
                              )}
                              value={bulkEtq[f.id] ?? sugeridas(detalle).etiqueta}
                              onChange={(id) => setBulkEtq((s) => ({ ...s, [f.id]: id }))}
                              textoVacio="Etiqueta…"
                            />
                            <button
                              onClick={() => registrarServicio(f.id, detalle)}
                              disabled={ocupado === f.id}
                              className="rounded-lg bg-emerald-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-emerald-700 disabled:opacity-50"
                            >
                              Registrar el gasto
                            </button>
                            <span className="text-xs text-slate-500">
                              Recibo sin artículos
                              {detalle.tipo_documento ? ` (${detalle.tipo_documento})` : ''}: un solo
                              gasto de {fmtMoney(f.monto_detectado)}
                            </span>
                          </>
                        ) : (
                          <>
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
                          </>
                        )}
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
                            <th className="py-1 pr-2" />
                            <th className="py-1 pr-3">Artículo</th>
                            <th className="py-1 pr-3">Valor</th>
                            <th className="py-1 pr-3">Etiqueta</th>
                            <th className="py-1 pr-3">Origen</th>
                            <th className="py-1" />
                          </tr>
                        </thead>
                        <tbody>
                          {detalle.lineas.map((l, i) => (
                            <tr key={l.id} className="border-t border-slate-200">
                              <td className="py-2 pr-2 align-top">
                                <div className="flex flex-col">
                                  <button
                                    onClick={() => void moverLinea(f.id, l.id, -1)}
                                    disabled={i === 0 || ocupado === f.id}
                                    title="Subir"
                                    className="text-xs leading-none text-slate-400 hover:text-indigo-600 disabled:opacity-30"
                                  >
                                    ▲
                                  </button>
                                  <button
                                    onClick={() => void moverLinea(f.id, l.id, 1)}
                                    disabled={i === detalle.lineas.length - 1 || ocupado === f.id}
                                    title="Bajar"
                                    className="text-xs leading-none text-slate-400 hover:text-indigo-600 disabled:opacity-30"
                                  >
                                    ▼
                                  </button>
                                </div>
                              </td>
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
                      No se detectaron artículos. Prueba con una foto más nítida, revisa el texto
                      extraído o añádelos a mano.
                    </p>
                  )}

                  {agregando === f.id ? (
                    <div className="mt-3 flex flex-wrap items-end gap-2 rounded-lg bg-slate-50 p-3">
                      <label className="text-xs text-slate-600">
                        Artículo
                        <input
                          value={nuevaLinea[f.id]?.descripcion ?? ''}
                          onChange={(e) =>
                            setNuevaLinea((s) => ({
                              ...s,
                              [f.id]: { ...(s[f.id] ?? { valor: '', etiqueta: '' }), descripcion: e.target.value },
                            }))
                          }
                          placeholder="Ej. PAN TAJADO"
                          className="mt-1 block w-64 rounded-lg border border-slate-300 px-3 py-1.5 text-sm"
                        />
                      </label>
                      <label className="text-xs text-slate-600">
                        Valor
                        <input
                          value={nuevaLinea[f.id]?.valor ?? ''}
                          onChange={(e) =>
                            setNuevaLinea((s) => ({
                              ...s,
                              [f.id]: { ...(s[f.id] ?? { descripcion: '', etiqueta: '' }), valor: e.target.value },
                            }))
                          }
                          inputMode="decimal"
                          placeholder="3200"
                          className="mt-1 block w-32 rounded-lg border border-slate-300 px-3 py-1.5 text-sm"
                        />
                      </label>
                      <label className="text-xs text-slate-600">
                        Etiqueta
                        <div className="mt-1 w-56">
                          <SelectBuscable
                            opciones={opcionesEtiquetas}
                            value={nuevaLinea[f.id]?.etiqueta ?? ''}
                            onChange={(id) =>
                              setNuevaLinea((s) => ({
                                ...s,
                                [f.id]: { ...(s[f.id] ?? { descripcion: '', valor: '' }), etiqueta: id },
                              }))
                            }
                            textoVacio="Sin etiqueta"
                          />
                        </div>
                      </label>
                      <button
                        onClick={() => void agregarLinea(f.id)}
                        disabled={ocupado === f.id || !(nuevaLinea[f.id]?.descripcion ?? '').trim()}
                        className="rounded-lg bg-emerald-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-emerald-700 disabled:opacity-50"
                      >
                        {ocupado === f.id ? 'Añadiendo…' : 'Añadir artículo'}
                      </button>
                      <button
                        onClick={() => setAgregando(null)}
                        className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm text-slate-700 hover:bg-white"
                      >
                        Cancelar
                      </button>
                      <span className="text-xs text-slate-500">
                        Queda como manual: volver a leer la factura no lo borra.
                      </span>
                    </div>
                  ) : (
                    <button
                      onClick={() => setAgregando(f.id)}
                      className="mt-3 rounded-lg border border-slate-300 px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-50"
                    >
                      ➕ Añadir artículo a mano
                    </button>
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
                    <button
                      onClick={() => {
                        setTextoEditando((s) => ({ ...s, [f.id]: f.texto_extraido ?? '' }))
                        setCorrigiendoTexto(f.id)
                      }}
                      className="rounded-lg border border-indigo-300 px-3 py-1 text-xs font-medium text-indigo-700 hover:bg-indigo-50"
                    >
                      ✏️ Corregir el texto y volver a leer
                    </button>
                    <span className="text-xs text-slate-500">
                      Es el texto completo que leyó Konta, no un fragmento. Si algo salió mal,
                      arréglalo aquí: es la forma de resolverlo sin depender del lector.
                    </span>
                  </div>
                  {corrigiendoTexto === f.id ? (
                    <div className="mt-2">
                      <textarea
                        value={textoEditando[f.id] ?? ''}
                        onChange={(e) =>
                          setTextoEditando((s) => ({ ...s, [f.id]: e.target.value }))
                        }
                        rows={14}
                        className="w-full rounded-lg border border-slate-300 p-3 font-mono text-xs"
                      />
                      <div className="mt-2 flex flex-wrap items-center gap-2">
                        <button
                          onClick={() => void guardarTextoYLeer(f.id)}
                          disabled={ocupado === f.id}
                          className="rounded-lg bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
                        >
                          {ocupado === f.id ? 'Leyendo…' : 'Guardar y volver a leer'}
                        </button>
                        <button
                          onClick={() => setCorrigiendoTexto(null)}
                          className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-50"
                        >
                          Cancelar
                        </button>
                        <span className="text-xs text-slate-500">
                          Se guarda como el texto de esta factura y se re-detectan el monto y la
                          fecha. Lo que ya estaba confirmado no se toca.
                        </span>
                      </div>
                    </div>
                  ) : (
                    <pre className="mt-2 max-h-72 overflow-auto whitespace-pre-wrap rounded-lg bg-slate-50 p-3 text-xs text-slate-600">
                      {f.texto_extraido}
                    </pre>
                  )}
                </details>
              )}
            </li>
          )
        })}
        {/* Si la carga falló no se puede decir «aún no has subido facturas»: eso afirma que
            la lista está vacía, y lo que pasa es que no se pudo leer. */}
        {items.length === 0 &&
          (error ? (
            <p className="text-sm text-amber-600">
              No se pudieron cargar las facturas ({error}). Vuelve a intentarlo en un momento.
            </p>
          ) : (
            <p className="text-sm text-slate-500">Aún no has subido facturas.</p>
          ))}
      </ul>
    </div>
  )
}
