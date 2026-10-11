import React, { useEffect, useState } from 'react'
import { useNavigate } from '../router'
import { AUTH_NOTICE_KEY, useAuth } from '../context/AuthContext'
import { API_BASE_URL } from '../config'
import axios from 'axios'
import logoEye from '../assets/dark-signal-logo-eye.svg'
import './Login.css'

function Login() {
  const navigate = useNavigate()
  const { login } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [authNotice] = useState(() => {
    const reason = new URLSearchParams(window.location.search).get('reason')
    if (reason === 'session-expired') {
      return 'Your session has expired. Please sign in again.'
    }
    return sessionStorage.getItem(AUTH_NOTICE_KEY) || ''
  })
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [isForgotOpen, setIsForgotOpen] = useState(false)
  const [forgotEmail, setForgotEmail] = useState('')
  const [forgotStatus, setForgotStatus] = useState('')
  const [isForgotSubmitting, setIsForgotSubmitting] = useState(false)
  const [showBootstrap, setShowBootstrap] = useState(false)
  const [bootstrapData, setBootstrapData] = useState({
    token: '',
    fullName: '',
    email: '',
    password: '',
  })
  const [bootstrapStatus, setBootstrapStatus] = useState('')
  const apiBase = API_BASE_URL

  useEffect(() => {
    sessionStorage.removeItem(AUTH_NOTICE_KEY)
    if (new URLSearchParams(window.location.search).has('reason')) {
      window.history.replaceState({}, '', '/login')
    }
  }, [])

  const getErrorMessage = (err, fallback) => {
    const detail = err?.response?.data?.detail
    const message = err?.response?.data?.message
    if (Array.isArray(detail)) {
      return detail.map((item) => item?.msg).filter(Boolean).join(', ') || fallback
    }
    return detail || message || fallback
  }

  const handleSubmit = async (event) => {
    event.preventDefault()
    setError('')
    setIsSubmitting(true)
    try {
      await login(email, password)
      navigate('/')
    } catch (err) {
      setError(getErrorMessage(err, 'Login failed.'))
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleBootstrap = async (event) => {
    event.preventDefault()
    setBootstrapStatus('')
    try {
      await axios.post(
        `${apiBase}/auth/bootstrap`,
        {
          token: bootstrapData.token,
          email: bootstrapData.email,
          password: bootstrapData.password,
          full_name: bootstrapData.fullName || null,
        },
        {
          headers: bootstrapData.token ? { 'X-Bootstrap-Token': bootstrapData.token } : {},
        }
      )
      setBootstrapStatus('Admin created. You can now sign in.')
      setShowBootstrap(false)
      setEmail(bootstrapData.email)
      setPassword('')
    } catch (err) {
      setBootstrapStatus(getErrorMessage(err, 'Bootstrap failed.'))
    }
  }

  const handleForgotPassword = async (event) => {
    event.preventDefault()
    setForgotStatus('')
    setIsForgotSubmitting(true)
    try {
      const response = await axios.post(`${apiBase}/auth/forgot-password`, { email: forgotEmail })
      setForgotStatus(
        response.data?.message || 'If the account exists, a reset link has been sent. Check your inbox and spam.'
      )
    } catch (err) {
      setForgotStatus(getErrorMessage(err, 'Failed to request reset.'))
    } finally {
      setIsForgotSubmitting(false)
    }
  }

  return (
    <div className="login-page">
      <div className="login-card">
        <div className="login-header">
          <div className="login-brand">
            <div className="login-mark">
              <img className="login-logo" src={logoEye} alt="Dark Signal" />
            </div>
            <div>
              <h1>Dark Signal</h1>
              <p>Secure phishing awareness platform</p>
            </div>
          </div>
          <div className="login-subtitle">Sign in to continue</div>
        </div>
        {authNotice && <div className="login-notice" role="status">{authNotice}</div>}
        <form onSubmit={handleSubmit}>
          <label className="field">
            Email
            <input
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              placeholder="you@company.com"
              required
            />
          </label>
          <label className="field">
            Password
            <input
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              placeholder="Your password"
              required
            />
          </label>
          {error && <div className="login-error">{error}</div>}
          <button
            type="button"
            className="forgot-link"
            onClick={() => {
              setForgotEmail(email)
              setForgotStatus('')
              setIsForgotOpen(true)
            }}
          >
            Forgot password?
          </button>
          <button className="action-btn primary-btn login-btn" type="submit" disabled={isSubmitting}>
            {isSubmitting ? 'Signing in...' : 'Sign In'}
          </button>
        </form>
        <button
          type="button"
          className="bootstrap-toggle"
          onClick={() => setShowBootstrap((prev) => !prev)}
        >
          {showBootstrap ? 'Hide bootstrap admin' : 'Create first admin'}
        </button>
        {showBootstrap && (
          <form className="bootstrap-form" onSubmit={handleBootstrap}>
            <label className="field">
              Bootstrap token
              <input
                type="password"
                value={bootstrapData.token}
                onChange={(event) => setBootstrapData({ ...bootstrapData, token: event.target.value })}
                placeholder="Provided by admin"
                required
              />
            </label>
            <label className="field">
              Full name
              <input
                type="text"
                value={bootstrapData.fullName}
                onChange={(event) => setBootstrapData({ ...bootstrapData, fullName: event.target.value })}
                placeholder="Dark Signal Admin"
              />
            </label>
            <label className="field">
              Admin email
              <input
                type="email"
                value={bootstrapData.email}
                onChange={(event) => setBootstrapData({ ...bootstrapData, email: event.target.value })}
                placeholder="admin@company.com"
                required
              />
            </label>
            <label className="field">
              Admin password
              <input
                type="password"
                minLength={8}
                maxLength={128}
                value={bootstrapData.password}
                onChange={(event) => setBootstrapData({ ...bootstrapData, password: event.target.value })}
                placeholder="Create a strong password"
                required
              />
            </label>
            {bootstrapStatus && <div className="login-error">{bootstrapStatus}</div>}
            <button className="action-btn secondary-btn login-btn" type="submit">
              Bootstrap Admin
            </button>
          </form>
        )}
      </div>

      {isForgotOpen && (
        <div className="modal-backdrop" onClick={() => setIsForgotOpen(false)}>
          <div className="modal" onClick={(event) => event.stopPropagation()}>
            <div className="modal-header">
              <h3>Reset your password</h3>
              <button className="icon-btn" onClick={() => setIsForgotOpen(false)}>✕</button>
            </div>
            <form className="modal-body" onSubmit={handleForgotPassword}>
              <label className="field">
                Email address
                <input
                  type="email"
                  value={forgotEmail}
                  onChange={(event) => setForgotEmail(event.target.value)}
                  placeholder="you@company.com"
                  required
                />
              </label>
              {forgotStatus && <div className="login-error">{forgotStatus}</div>}
              <div className="modal-footer">
                <button className="action-btn secondary-btn" type="button" onClick={() => setIsForgotOpen(false)}>
                  Cancel
                </button>
                <button className="action-btn primary-btn" type="submit" disabled={isForgotSubmitting}>
                  {isForgotSubmitting ? 'Sending...' : 'Send reset link'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}

export default Login
