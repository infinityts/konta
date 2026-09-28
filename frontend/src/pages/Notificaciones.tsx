import { useEffect, useState } from 'react'
import { api } from '../api'
import type { ChatTelegram, Notificaciones as Config } from '../types'

export default function Notificaciones() {
  const [cfg, setCfg] = useState<Config | null>(null)
  const [chats, setChats] = useState<ChatTelegram[]>([])
  const [mensaje, setMensaje] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    api<Config>('/notificaciones')
      .then(setCfg)
      .catch((e) => setError(e instanceof Error ? e.message : 'Error'))
  }, [])

  async function guardar() {
    if (!cfg) return
    setError('')
    setMensaje('')
    try {
      const r = await api<Config>('/notificaciones', {
        method: 'PUT',
        body: JSON.stringify({
          canal: cfg.canal,
          telegram_chat_id: cfg.telegram_chat_id || null,
          whatsapp_numero: cfg.whatsapp_numero || null,
          email: cfg.email || null,
          dias_anticipacion: Number(cfg.dias_anticipacion),
          activo: cfg.activo,
        }),
      })
      setCfg(r)
      setMensaje('✅ Configuración guardada.')
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Error al guardar')
    }
  }

  async function detectar() {
    setError('')
    setMensaje('')
    try {
      const r = await api<{ chats: ChatTelegram[] }>('/notificaciones/telegram/detectar', { method: 'POST' })
      setChats(r.chats)
      setMensaje(r.chats.length ? 'Escribe al bot y elige tu chat:' : 'No encontré chats. Escríbele algo a tu bot en Telegram y reintenta.')
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Error al detectar')
    }
  }

  async function probar() {
    setError('')
    setMensaje('')
    try {
      const r = await api<{ enviados: string[]; alertas: number }>('/notificaciones/probar', { method: 'POST' })
      setMensaje(`✅ Prueba enviada por: ${r.enviados.join(', ')} (${r.alertas} alerta(s)).`)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Error al enviar la prueba')
    }
  }

  const set = <K extends keyof Config>(k: K, v: Config[K]) => setCfg((c) => (c ? { ...c, [k]: v } : c))

  return (
    <div>
      <h2 className="text-xl font-semibold">Notificaciones</h2>
      <p className="mt-1 text-sm text-slate-500">
        Recibe un resumen de tus próximos pagos por Telegram y/o correo. Se envía como máximo
        <strong> una vez al día</strong>.
      </p>
      {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
      {mensaje && <p className="mt-2 text-sm text-emerald-700">{mensaje}</p>}

      {cfg && (
        <div className="mt-4 rounded-xl border border-slate-200 bg-white p-5">
          <label className="flex items-center gap-3 text-sm font-medium">
            <input type="checkbox" checked={cfg.activo} onChange={(e) => set('activo', e.target.checked)} className="h-4 w-4" />
            Activar notificaciones
          </label>

          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            <div>
              <label className="text-sm text-slate-600">Canal</label>
              <select value={cfg.canal} onChange={(e) => set('canal', e.target.value as Config['canal'])} className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm">
                <option value="telegram">Telegram</option>
                <option value="email">Correo</option>
                <option value="whatsapp">WhatsApp</option>
                <option value="ambos">Telegram + correo</option>
                <option value="todos">Los tres</option>
              </select>
            </div>
            <div>
              <label className="text-sm text-slate-600">Días de anticipación</label>
              <input type="number" min={1} max={60} value={cfg.dias_anticipacion} onChange={(e) => set('dias_anticipacion', Number(e.target.value))} className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" />
            </div>

            <div className="sm:col-span-2">
              <label className="text-sm text-slate-600">Telegram chat ID</label>
              <div className="mt-1 flex flex-wrap gap-2">
                <input value={cfg.telegram_chat_id ?? ''} onChange={(e) => set('telegram_chat_id', e.target.value)} placeholder="Ej. 123456789" className="flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm" />
                <button onClick={detectar} className="rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-700 hover:bg-slate-50">Detectar</button>
              </div>
              {chats.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-2">
                  {chats.map((c) => (
                    <button key={c.chat_id} onClick={() => set('telegram_chat_id', c.chat_id)} className="rounded-full border border-indigo-200 bg-indigo-50 px-3 py-1 text-xs text-indigo-700 hover:bg-indigo-100">
                      {c.nombre || 'chat'} · {c.chat_id}
                    </button>
                  ))}
                </div>
              )}
            </div>

            <div className="sm:col-span-2">
              <label className="text-sm text-slate-600">WhatsApp (número destino)</label>
              <input
                value={cfg.whatsapp_numero ?? ''}
                onChange={(e) => set('whatsapp_numero', e.target.value)}
                placeholder="573001234567 (internacional, sin +)"
                className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
              />
            </div>

            <div className="sm:col-span-2">
              <label className="text-sm text-slate-600">Correo destino</label>
              <input value={cfg.email ?? ''} onChange={(e) => set('email', e.target.value)} placeholder="tu@correo.com" className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" />
            </div>
          </div>

          <div className="mt-4 flex flex-wrap gap-2">
            <button onClick={guardar} className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700">Guardar</button>
            <button onClick={probar} className="rounded-lg border border-slate-300 px-4 py-2 text-sm text-slate-700 hover:bg-slate-50">Enviar prueba</button>
          </div>

          {cfg.ultima_notificacion && (
            <p className="mt-3 text-xs text-slate-500">Última notificación enviada: {cfg.ultima_notificacion}</p>
          )}
        </div>
      )}

      <div className="mt-4 rounded-xl border border-slate-200 bg-slate-50 p-5 text-sm text-slate-600">
        <p className="font-medium text-slate-700">Cómo conectar cada canal</p>
        <ul className="mt-2 list-disc space-y-1 pl-5">
          <li>
            <strong>Telegram:</strong> crea un bot con <em>@BotFather</em> y define
            <code className="mx-1 rounded bg-white px-1">FINANZAS_TELEGRAM_BOT_TOKEN</code> en el servidor.
            Luego escríbele algo a tu bot y pulsa <em>Detectar</em>.
          </li>
          <li>
            <strong>Correo:</strong> define <code className="mx-1 rounded bg-white px-1">FINANZAS_SMTP_HOST</code>,
            <code className="mx-1 rounded bg-white px-1">FINANZAS_SMTP_USER</code>,
            <code className="mx-1 rounded bg-white px-1">FINANZAS_SMTP_PASSWORD</code> y
            <code className="mx-1 rounded bg-white px-1">FINANZAS_SMTP_FROM</code> en el servidor.
          </li>
          <li>
            <strong>WhatsApp:</strong> (próximamente) requeriría la Cloud API de Meta o un gateway de terceros.
          </li>
        </ul>
      </div>
    </div>
  )
}
