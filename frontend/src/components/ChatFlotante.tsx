import { useState } from 'react'
import ChatAsistente from './ChatAsistente'

/**
 * El asistente **siempre a mano**, abajo a la derecha, en cualquier pantalla.
 *
 * Antes había que entrar en Herramientas → Asistente para preguntar algo, y eso es pedirle al
 * cliente que se acuerde de dónde está. Aquí está en todas las pantallas: se abre, se pregunta y se
 * cierra sin perder el hilo de la conversación (el chat sigue montado, solo se oculta).
 */
export default function ChatFlotante() {
  const [abierto, setAbierto] = useState(false)

  return (
    <>
      <button
        onClick={() => setAbierto((v) => !v)}
        title={abierto ? 'Cerrar el asistente' : 'Preguntarle al asistente'}
        aria-label={abierto ? 'Cerrar el asistente' : 'Abrir el asistente'}
        className={`fixed bottom-5 right-5 z-40 flex items-center gap-2 rounded-full px-4 py-3 text-sm font-medium text-white shadow-lg transition ${
          abierto ? 'bg-slate-700 hover:bg-slate-800' : 'bg-indigo-600 hover:bg-indigo-700'
        }`}
      >
        <span className="text-lg leading-none">{abierto ? '✕' : '💬'}</span>
        <span className="hidden sm:inline">{abierto ? 'Cerrar' : 'Asistente'}</span>
      </button>

      <div
        className={`fixed bottom-20 right-5 z-40 flex h-[32rem] max-h-[calc(100vh-7rem)] w-[24rem] max-w-[calc(100vw-2.5rem)] flex-col rounded-2xl border border-slate-200 bg-white p-3 shadow-2xl ${
          abierto ? '' : 'hidden'
        }`}
        role="dialog"
        aria-label="Asistente de Konta"
      >
        <ChatAsistente compacto />
      </div>
    </>
  )
}
