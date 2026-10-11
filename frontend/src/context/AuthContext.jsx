import React, { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react'
import axios from 'axios'
import { API_BASE_URL } from '../config'

const AuthContext = createContext(null)
const TOKEN_STORAGE_KEY = 'dark_signal_token'
const EMAIL_STORAGE_KEY = 'dark_signal_user_email'
const ROLE_STORAGE_KEY = 'dark_signal_user_role'
export const AUTH_NOTICE_KEY = 'dark_signal_auth_notice'
const SESSION_EXPIRED_MESSAGE = 'Your session has expired. Please sign in again.'
const SESSION_EXPIRED_PATH = '/login?reason=session-expired'

const parseJwt = (jwtToken) => {
  try {
    const base64 = jwtToken.split('.')[1]
    const padded = base64.padEnd(base64.length + ((4 - (base64.length % 4)) % 4), '=')
    const normalized = padded.replace(/-/g, '+').replace(/_/g, '/')
    return JSON.parse(atob(normalized))
  } catch (error) {
    return null
  }
}

const getTokenExpiration = (jwtToken) => {
  const expiration = Number(parseJwt(jwtToken)?.exp)
  return Number.isFinite(expiration) ? expiration * 1000 : null
}

const clearStoredSession = () => {
  delete axios.defaults.headers.common.Authorization
  localStorage.removeItem(TOKEN_STORAGE_KEY)
  localStorage.removeItem(EMAIL_STORAGE_KEY)
  localStorage.removeItem(ROLE_STORAGE_KEY)
}

export function AuthProvider({ children }) {
  const isHandlingUnauthorized = useRef(false)
  const [token, setToken] = useState(() => {
    const stored = localStorage.getItem(TOKEN_STORAGE_KEY)
    const expiresAt = stored ? getTokenExpiration(stored) : null
    if (stored && expiresAt && expiresAt > Date.now()) {
      axios.defaults.headers.common.Authorization = `Bearer ${stored}`
      return stored
    }
    if (stored) {
      clearStoredSession()
      sessionStorage.setItem(AUTH_NOTICE_KEY, SESSION_EXPIRED_MESSAGE)
    }
    return null
  })
  const [userEmail, setUserEmail] = useState(() => localStorage.getItem(EMAIL_STORAGE_KEY))
  const [userRole, setUserRole] = useState(() => localStorage.getItem(ROLE_STORAGE_KEY))

  const clearSession = useCallback(() => {
    clearStoredSession()
    setToken(null)
    setUserEmail(null)
    setUserRole(null)
  }, [])

  const expireSession = useCallback(() => {
    if (isHandlingUnauthorized.current) return
    isHandlingUnauthorized.current = true
    sessionStorage.setItem(AUTH_NOTICE_KEY, SESSION_EXPIRED_MESSAGE)
    clearSession()
    if (window.location.pathname !== '/login') {
      window.location.replace(SESSION_EXPIRED_PATH)
    }
  }, [clearSession])

  useEffect(() => {
    if (token) {
      isHandlingUnauthorized.current = false
      axios.defaults.headers.common.Authorization = `Bearer ${token}`
      localStorage.setItem(TOKEN_STORAGE_KEY, token)
      const payload = parseJwt(token)
      const role = payload?.role || null
      setUserRole(role)
    } else {
      delete axios.defaults.headers.common.Authorization
      localStorage.removeItem(TOKEN_STORAGE_KEY)
      setUserRole(null)
    }
  }, [token])

  useEffect(() => {
    if (userEmail) {
      localStorage.setItem(EMAIL_STORAGE_KEY, userEmail)
    } else {
      localStorage.removeItem(EMAIL_STORAGE_KEY)
    }
  }, [userEmail])

  useEffect(() => {
    if (userRole) {
      localStorage.setItem(ROLE_STORAGE_KEY, userRole)
    } else {
      localStorage.removeItem(ROLE_STORAGE_KEY)
    }
  }, [userRole])

  useEffect(() => {
    if (!token) return undefined
    const expiresAt = getTokenExpiration(token)
    if (!expiresAt || expiresAt <= Date.now()) {
      expireSession()
      return undefined
    }
    const timerId = window.setTimeout(expireSession, expiresAt - Date.now())
    return () => window.clearTimeout(timerId)
  }, [expireSession, token])

  useEffect(() => {
    const interceptorId = axios.interceptors.response.use(
      (response) => response,
      (error) => {
        const requestUrl = String(error?.config?.url || '')
        const isPublicAuthRequest = /\/auth\/(token|forgot-password|reset-password|bootstrap)/.test(requestUrl)
        if (error?.response?.status === 401 && token && !isPublicAuthRequest) {
          expireSession()
        }
        return Promise.reject(error)
      }
    )
    return () => axios.interceptors.response.eject(interceptorId)
  }, [expireSession, token])

  const login = async (email, password) => {
    const response = await axios.post(`${API_BASE_URL}/auth/token`, { email, password })
    const accessToken = response.data.access_token
    sessionStorage.removeItem(AUTH_NOTICE_KEY)
    axios.defaults.headers.common.Authorization = `Bearer ${accessToken}`
    setToken(accessToken)
    setUserEmail(email)
    const payload = parseJwt(accessToken)
    setUserRole(payload?.role || null)
  }

  const logout = () => {
    sessionStorage.removeItem(AUTH_NOTICE_KEY)
    clearSession()
  }

  const value = useMemo(
    () => ({
      token,
      userEmail,
      userRole,
      isAuthenticated: Boolean(token),
      login,
      logout,
    }),
    [clearSession, token, userEmail, userRole]
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider')
  }
  return context
}
