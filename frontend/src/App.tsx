import type { ReactNode } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { useAuth } from './auth'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import IngresosRecurrentes from './pages/IngresosRecurrentes'
import Login from './pages/Login'
import Register from './pages/Register'
import Suscripciones from './pages/Suscripciones'
import Tarjetas from './pages/Tarjetas'
import Transacciones from './pages/Transacciones'

function Protected({ children }: { children: ReactNode }) {
  const { token } = useAuth()
  return token ? <>{children}</> : <Navigate to="/login" replace />
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route
        element={
          <Protected>
            <Layout />
          </Protected>
        }
      >
        <Route path="/" element={<Dashboard />} />
        <Route path="/tarjetas" element={<Tarjetas />} />
        <Route path="/suscripciones" element={<Suscripciones />} />
        <Route path="/ingresos-recurrentes" element={<IngresosRecurrentes />} />
        <Route path="/transacciones" element={<Transacciones />} />
      </Route>
    </Routes>
  )
}
