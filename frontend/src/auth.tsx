import { createContext, useContext, useState, type ReactNode } from 'react'
import { api } from './api'

interface User {
  id: string
  email: string
  nombre: string
  moneda_principal: string
}

interface AuthContextType {
  token: string | null
  user: User | null
  login: (email: string, password: string) => Promise<void>
  register: (email: string, nombre: string, password: string) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthContextType | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem('konta_token'))
  const [user, setUser] = useState<User | null>(null)

  async function login(email: string, password: string) {
    const data = await api<{ access_token: string }>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    })
    localStorage.setItem('konta_token', data.access_token)
    setToken(data.access_token)
    const me = await api<User>('/auth/me')
    setUser(me)
  }

  async function register(email: string, nombre: string, password: string) {
    await api('/auth/register', {
      method: 'POST',
      body: JSON.stringify({ email, nombre, password }),
    })
    await login(email, password)
  }

  function logout() {
    localStorage.removeItem('konta_token')
    setToken(null)
    setUser(null)
  }

  return (
    <AuthContext.Provider value={{ token, user, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth debe usarse dentro de AuthProvider')
  return ctx
}
