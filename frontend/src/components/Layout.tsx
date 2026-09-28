import { Suspense } from 'react'
import { Outlet } from 'react-router-dom'
import TopNav from './TopNav'
import { Cargando } from './loading-ui/cargando'

/**
 * Marco de la aplicación: barra superior agrupada + contenido a ancho completo.
 *
 * El `Suspense` vive aquí (alrededor del `Outlet`) para que, mientras baja el
 * código de una página, se vea el loader **sin que desaparezca la navegación**.
 */
export default function Layout() {
  return (
    <div className="min-h-screen">
      <TopNav />
      <main className="mx-auto w-full max-w-[1500px] px-5 py-6">
        <Suspense fallback={<Cargando texto="Cargando página…" />}>
          <Outlet />
        </Suspense>
      </main>
    </div>
  )
}
